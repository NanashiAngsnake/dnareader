# -*- coding: utf-8 -*-

import asyncio
import io

from PIL import Image, ImageFilter, ImageOps
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

_engine = None

_engine_lock = asyncio.Lock()


def get_engine():
    global _engine
    if _engine is None:
        if not OcrEngine.is_language_supported(Language("ja")):
            raise RuntimeError(
                "OCR japonais non installé. Paramètres Windows → Heure et langue "
                "→ Langue → Ajouter le japonais (avec la reconnaissance optique).")
        _engine = OcrEngine.try_create_from_language(Language("ja"))
    return _engine


def _enhance(img: Image.Image, mode: str) -> Image.Image:
    if mode == "off":
        return img
    out = ImageOps.autocontrast(img.convert("L"), cutoff=0)
    if mode == "boost":
        out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    return out.convert("RGB")


MAX_PIXELS = 40_000_000
MAX_PIXELS_BOOST = 999_000_000


def _prepare(img: Image.Image, enhance: str = "auto"):
    img = _enhance(img, enhance)
    px = max(img.width * img.height, 1)
    cap = MAX_PIXELS_BOOST if enhance == "boost" else MAX_PIXELS
    scale = min(3.0, (cap / px) ** 0.5)
    scale = min(scale, (OcrEngine.max_image_dimension - 4) / max(img.width, img.height))
    scale = max(scale, 0.05)
    if abs(scale - 1.0) > 0.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)),
                         Image.LANCZOS)
    return img, scale


def _looks_wrong(lines) -> bool:
    if not lines:
        return True
    tiny = sum(1 for l in lines if len(l["text"].strip()) <= 2)
    has_real_line = any(len(l["text"].strip()) >= 5 for l in lines)
    return (not has_real_line) or (tiny >= max(3, 0.6 * len(lines)))


def _quality(lines) -> int:
    score = 0
    for l in lines:
        n = len(l["text"].strip())
        score += n + (6 if n >= 5 else 0)
    return score


async def ocr_image(img: Image.Image, enhance: str = "auto"):
    img = img.convert("RGB")
    lines = await _ocr_once(img, enhance)
    if not _weak(lines):
        return lines

    best = lines
    candidates = [(1.5, enhance)]
    if enhance == "auto":
        candidates.append((None, "boost"))
    for hint, enh in candidates:
        alt = await _ocr_once(img, enh, scale_hint=hint)
        best = _merge(best, alt)
        if not _weak(best):
            break
    return _reading_order(best)


def _overlap(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    small = min(aw * ah, bw * bh) or 1
    return inter / small


def _merge(a, b):
    out = list(a)
    for cand in b:
        placed = False
        for i, ref in enumerate(out):
            if _overlap(ref["box"], cand["box"]) > 0.5:
                if len(cand["text"].strip()) > len(ref["text"].strip()):
                    out[i] = cand
                placed = True
                break
        if not placed:
            out.append(cand)
    return out


def _weak(lines) -> bool:
    if _looks_wrong(lines):
        return True
    return len(lines) <= 2 and sum(len(l["text"].strip()) for l in lines) < 24


def _prepare_bytes(img: Image.Image, enhance: str, scale_hint: float | None):
    prepared, scale = _prepare(img, enhance)
    if scale_hint and abs(scale_hint - scale) > 0.05:
        base = _enhance(img, enhance)
        w, h = int(base.width * scale_hint), int(base.height * scale_hint)
        prepared = base.resize((w, h), Image.LANCZOS) if scale_hint != 1.0 else base
        scale = scale_hint
    buf = io.BytesIO()
    prepared.save(buf, format="BMP")
    return buf.getvalue(), scale


async def _ocr_once(img: Image.Image, enhance: str, scale_hint: float | None = None):
    engine = get_engine()
    data, scale = await asyncio.to_thread(_prepare_bytes, img, enhance, scale_hint)

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(data)
    await writer.store_async()
    await writer.flush_async()

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    async with _engine_lock:
        result = await engine.recognize_async(bitmap)

    lines = []
    for line in result.lines:
        text_parts = []
        char_boxes = []
        for word in line.words:
            wtext = word.text
            r = word.bounding_rect
            n = max(len(wtext), 1)
            cw = r.width / n
            for i, ch in enumerate(wtext):
                text_parts.append(ch)
                char_boxes.append([
                    (r.x + i * cw) / scale, r.y / scale,
                    cw / scale, r.height / scale,
                ])
        text = "".join(text_parts)
        if not text.strip():
            continue
        xs = [b[0] for b in char_boxes]
        ys = [b[1] for b in char_boxes]
        x2 = max(b[0] + b[2] for b in char_boxes)
        y2 = max(b[1] + b[3] for b in char_boxes)
        lines.append({
            "text": text,
            "box": [min(xs), min(ys), x2 - min(xs), y2 - min(ys)],
            "chars": char_boxes,
        })
    return _reading_order(lines)


def taux_encre(img: Image.Image, box) -> float:
    try:
        x, y, w, h = (int(v) for v in box[:4])
        x, y = max(0, x), max(0, y)
        w, h = min(w, img.width - x), min(h, img.height - y)
        if w < 4 or h < 4:
            return 0.0
        g = img.crop((x, y, x + w, y + h)).convert("L")
        hist = g.histogram()
        fond = hist.index(max(hist))
        loin = sum(c for v, c in enumerate(hist) if abs(v - fond) > 60)
        return loin / float(w * h)
    except Exception:
        return 1.0


ENCRE_MIN, ENCRE_MAX = 0.004, 0.85


def sans_encre(img: Image.Image, lines):
    gardees = []
    for l in lines:
        e = taux_encre(img, l.get("box") or [0, 0, 0, 0])
        l["encre"] = round(e, 4)
        if e < ENCRE_MIN:
            continue
        l["sature"] = e > ENCRE_MAX
        gardees.append(l)
    return gardees


def _reading_order(lines):
    if len(lines) < 2:
        return lines
    with_center = []
    for l in lines:
        x, y, w, h = l["box"]
        with_center.append((y + h / 2, x, h, l))
    with_center.sort(key=lambda t: t[0])

    rows, current = [], [with_center[0]]
    for item in with_center[1:]:
        cy, _, h, _ = item
        ref_cy = current[0][0]
        ref_h = max(current[0][2], h, 1)
        if abs(cy - ref_cy) <= ref_h * 0.6:
            current.append(item)
        else:
            rows.append(current)
            current = [item]
    rows.append(current)

    out = []
    for row in rows:
        row.sort(key=lambda t: t[1])
        out.extend(_join_row(t[3] for t in row))
    return out


def _join_row(items):
    items = list(items)
    if len(items) < 2:
        return items
    out = [items[0]]
    for cur in items[1:]:
        prev = out[-1]
        px, _, pw, ph = prev["box"]
        cx = cur["box"][0]
        gap = cx - (px + pw)
        if 0 <= gap <= max(ph, 1) * 4:
            merged_chars = prev["chars"] + cur["chars"]
            xs = [b[0] for b in merged_chars]
            ys = [b[1] for b in merged_chars]
            x2 = max(b[0] + b[2] for b in merged_chars)
            y2 = max(b[1] + b[3] for b in merged_chars)
            out[-1] = {
                "text": prev["text"] + cur["text"],
                "box": [min(xs), min(ys), x2 - min(xs), y2 - min(ys)],
                "chars": merged_chars,
            }
        else:
            out.append(cur)
    return out

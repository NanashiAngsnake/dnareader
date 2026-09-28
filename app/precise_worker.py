# -*- coding: utf-8 -*-
import base64
import io
import json
import os
import sys
from pathlib import Path


def _add_torch_dll_dir():
    if sys.platform != "win32":
        return None
    try:
        import importlib.util
        spec = importlib.util.find_spec("torch")
        if spec and spec.origin:
            lib = Path(spec.origin).parent / "lib"
            if lib.is_dir():
                return os.add_dll_directory(str(lib))
    except Exception:
        pass
    return None


_DLL_HANDLE = _add_torch_dll_dir()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    out = sys.stdout
    try:
        from PIL import Image
        import torch
        torch.set_num_threads(4)
        from manga_ocr import MangaOcr
        mocr = MangaOcr()
    except Exception as e:
        out.write(json.dumps({"fatal": str(e)}) + "\n")
        out.flush()
        return 1

    out.write(json.dumps({"ready": True}) + "\n")
    out.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get("quit"):
                break
            img = Image.open(io.BytesIO(base64.b64decode(req["img"]))).convert("RGB")
            out.write(json.dumps({"text": mocr(img)}) + "\n")
        except Exception as e:
            out.write(json.dumps({"error": str(e)}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

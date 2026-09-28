# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

MODEL = "facebook/nllb-200-distilled-600M"
SRC, TGT = "jpn_Jpan", "fra_Latn"

_tok = _mdl = _bos = None


def _load():
    global _tok, _mdl, _bos
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    _tok = AutoTokenizer.from_pretrained(MODEL, src_lang=SRC)
    _mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL)
    _mdl.eval()
    _bos = _tok.convert_tokens_to_ids(TGT)


def _translate(textes):
    import torch
    enc = _tok(textes, return_tensors="pt", padding=True, truncation=True,
               max_length=256)
    with torch.inference_mode():
        gen = _mdl.generate(**enc, forced_bos_token_id=_bos, max_new_tokens=160,
                            num_beams=1)
    return _tok.batch_decode(gen, skip_special_tokens=True)


def main():
    try:
        _load()
    except Exception as e:
        print(json.dumps({"fatal": f"{e.__class__.__name__}: {e}"}, ensure_ascii=True),
              flush=True)
        return
    print(json.dumps({"ready": True, "model": MODEL}, ensure_ascii=True), flush=True)

    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            req = json.loads(ligne)
        except Exception:
            continue
        if req.get("quit"):
            return
        textes = req.get("texts") or []
        try:
            out = _translate(textes) if textes else []
            rep = {"texts": out}
        except Exception as e:
            rep = {"error": f"{e.__class__.__name__}: {e}"}
        print(json.dumps(rep, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()

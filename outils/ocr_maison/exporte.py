# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import torch

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import donnees as D
from modele import CRNN, Alphabet


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    etat_f = D.SORTIE / "crnn.pt"
    if not etat_f.exists():
        print("aucun modele : lance d'abord entraine.py")
        return 1
    etat = torch.load(etat_f, map_location="cpu")
    alpha = Alphabet(etat["alphabet"])
    reseau = CRNN(len(alpha))
    reseau.load_state_dict(etat["reseau"])
    reseau.eval()

    D.MODELES.mkdir(parents=True, exist_ok=True)
    sortie = D.MODELES / "ocr_maison.onnx"
    exemple = torch.randn(1, 1, D.HAUTEUR, 512)
    torch.onnx.export(
        reseau, exemple, str(sortie),
        input_names=["bande"], output_names=["colonnes"],
        dynamic_axes={"bande": {0: "lot", 3: "largeur"},
                      "colonnes": {0: "lot", 1: "temps"}},
        opset_version=17, do_constant_folding=True)

    try:
        import onnx
        graphe = onnx.load(str(sortie))
        onnx.save_model(graphe, str(sortie), save_as_external_data=False)
        annexe = sortie.with_suffix(".onnx.data")
        if annexe.exists():
            annexe.unlink()
    except Exception as e:
        print(f"  (poids laisses a cote : {e})")

    (D.MODELES / "ocr_maison_alphabet.txt").write_text(
        etat["alphabet"], encoding="utf-8")
    (D.MODELES / "ocr_maison.json").write_text(json.dumps({
        "hauteur": D.HAUTEUR,
        "pas_colonne": 8,
        "classes": len(alpha),
        "pas_entrainement": etat.get("pas"),
        "cer_synthese": etat.get("cer"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    try:
        import numpy as np
        import onnxruntime as ort
        s = ort.InferenceSession(str(sortie), providers=["CPUExecutionProvider"])
        for largeur in (256, 512, 1024):
            x = torch.randn(1, 1, D.HAUTEUR, largeur)
            with torch.no_grad():
                attendu = reseau(x).numpy()
            obtenu = s.run(None, {"bande": x.numpy()})[0]
            ecart = float(np.abs(attendu - obtenu).max())
            print(f"  largeur {largeur:5d} : ecart max {ecart:.2e} "
                  f"({'identique' if ecart < 1e-3 else 'A REGARDER'})")
    except ImportError:
        print("  (onnxruntime absent du venv d'entrainement : verification sautee)")

    mo = sortie.stat().st_size / 1e6
    print(f"\n{sortie} — {mo:.1f} Mo")
    print(f"alphabet : {len(alpha)} classes")
    print("depose dans modeles/ : l'application le proposera au "
          "prochain lancement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

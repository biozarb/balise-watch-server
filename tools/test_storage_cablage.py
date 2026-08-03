#!/usr/bin/env python3
"""
test_storage_cablage.py — vérifie que les 5 chaînes écrivent bien via
`tools/storage.py`, avec LE cache_control qu'elles avaient avant.

À lancer depuis `balise-watch-server/` :
    python3 tools/test_storage_cablage.py

Pourquoi ce test existe : la factorisation du 03/08/2026 a remplacé cinq
`sb_upload()` par un adaptateur de deux lignes chacun. Le risque n'était
pas de casser bruyamment — c'était d'intervertir une politique de cache
entre deux chaînes. Un `max-age=21600` posé par erreur sur les tuiles de
vent rejouerait EXACTEMENT le bug des 23-24/07 (calques figés sur
certains ordis, hard-refresh sans effet), et il ne se verrait ni à la
compilation, ni au run, ni dans les logs : seulement chez un pilote,
plusieurs heures plus tard, et de façon intermittente.

C'est donc un test de la seule chose que la factorisation pouvait casser
en silence. Il ne touche ni le réseau, ni Supabase, ni R2.
"""
import importlib.util
import os
import sys
import types

os.environ["DRY_RUN"] = "1"
os.environ.setdefault("STORAGE_BACKEND", "supabase")

# Les chaînes importent eccodes / omfiles / scipy / matplotlib au niveau
# module. On ne veut ni les installer ni les exécuter : seul le câblage
# de l'upload nous intéresse.
for nom in ("eccodes", "omfiles", "fsspec", "numpy", "matplotlib",
            "matplotlib.pyplot", "scipy", "scipy.ndimage"):
    if nom not in sys.modules:
        m = types.ModuleType(nom)
        m.__getattr__ = lambda k: (lambda *a, **kw: None)
        m.use = lambda *a, **kw: None
        sys.modules[nom] = m

# Politique de cache attendue par chaîne. Cette table EST la spécification :
# clé stable réécrite en place → cache court ; clé horodatée immuable →
# cache long + purge obligatoire (cf. tools/storage.py).
ATTENDU = {
    "arome-wind":      "no-cache, must-revalidate",
    "arome-thermal":   "no-cache, must-revalidate",
    "arpege-thermal":  "no-cache, must-revalidate",
    "arome-gustfront": "no-cache, must-revalidate",
    "arpege-isobars":  "max-age=21600",
}


class Espion:
    """Remplace `Storage` : n'écrit rien, retient ce qu'on lui demande."""

    def __init__(self):
        self.vus = []

    def put(self, path, body, cache_control):
        self.vus.append((path, cache_control))


def main():
    ok = True
    for chaine, attendu in ATTENDU.items():
        spec = importlib.util.spec_from_file_location(
            chaine.replace("-", "_"), f"{chaine}/ingest.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)

        # Le module partagé est-il bien celui importé, et non une copie ?
        assert mod.Storage.__module__ == "storage", chaine
        assert callable(mod.verifier_dimensionnement), chaine

        mod.STORE = Espion()
        mod.sb_upload("x/y.json", b"{}")
        _, cc = mod.STORE.vus[0]
        if cc != attendu:
            ok = False
        print(f"  {'✓' if cc == attendu else '✗'} {chaine:<17} "
              f"défaut = {cc!r}" + ("" if cc == attendu else f"  ATTENDU {attendu!r}"))

    print("\n  câblage :", "OK" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Restructure naturals: one generic entry per colour name (Graham, 2026-07-19).

Price book stays per-supplier (pricing truth). In the library, every natural
colour gets ONE generic entry ("Natural Stone" supplier) holding the example
image; supplier-specific natural entries keep their identity for the price join
but share the generic's image and carry genericId.
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    prev_generics = {s["id"]: s for s in db["slabs"] if s["supplier"] == "Natural Stone"}
    slabs = [s for s in db["slabs"] if s["supplier"] != "Natural Stone"]  # idempotent
    groups = {}
    for s in slabs:
        if s["naturalStone"]:
            groups.setdefault(norm(s["colour"]), []).append(s)

    generics = []
    for key, members in groups.items():
        # display name: the most common raw spelling
        name = Counter(m["colour"] for m in members).most_common(1)[0][0]
        material = Counter(m["material"] for m in members).most_common(1)[0][0]
        best = None
        for m in members:
            if not m["image"]["file"]:
                continue
            rank = {"slab": 0, "representative": 1, "closeup-only": 2}.get(m["image"]["status"], 3)
            if best is None or rank < best[0]:
                best = (rank, m["image"])
        gid = f"natural--{slug(name)}"
        image = dict(best[1]) if best else {"file": "", "status": "missing", "source": "", "borrowedFrom": ""}
        image["borrowedFrom"] = ""
        prev = prev_generics.get(gid)
        if prev:  # keep hand-curated primary + gallery from earlier runs
            if prev["image"]["file"]:
                image = dict(prev["image"])
        generics.append({
            "id": gid,
            "supplier": "Natural Stone",
            "colour": name,
            "material": material,
            "naturalStone": True,
            "illustrationOnly": True,
            "thicknesses": sorted({t for m in members for t in m["thicknesses"]}),
            "productUrl": next((m["productUrl"] for m in members if m.get("productUrl")), ""),
            "image": image,
            "suppliers": sorted({m["supplier"] for m in members}),
            **({"images": prev["images"]} if prev and prev.get("images") else {}),
        })
        for m in members:
            m["genericId"] = gid
            if image["file"]:
                m["image"] = {"file": image["file"], "status": image["status"],
                              "source": image["source"], "borrowedFrom": f"shared natural image ({gid})"}

    db["slabs"] = slabs + generics
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    have = sum(1 for g in generics if g["image"]["file"])
    print(f"{len(generics)} generic natural colours created ({have} with images); "
          f"{sum(len(m) for m in groups.values())} supplier entries linked")


if __name__ == "__main__":
    main()

"""Import Chad Gage's (Bloomstones London) supplier photo zip into the slab library.

Source: "Quartz .zip" sent 2026-08-26 (1.9 GB, `All Quartz + Close Ups/<Colour>/...`).
Not a website harvest -- files come from a local extracted folder, so no curl.

    python bloom_chad_import.py --report            # match/plan table, changes nothing
    python bloom_chad_import.py --apply             # copy originals -> OneDrive, webps -> images/,
                                                    #   patch slabs.json (Bloomstones only), sheets + report
    python bloom_chad_import.py --zip "C:\\...\\Quartz .zip" --report   # extract first if --src is empty

Idempotent: every image this script writes carries `source` starting with SOURCE_TAG; on
re-run those gallery items are rebuilt from scratch and a main set by this script is
re-evaluated. Site mains (`status: slab`, non-Chad source) are never replaced -- Chad's slab
shots become extra `kind: slab` images (`{id}--alt{n}.webp`) instead. Follows HARVEST-SPEC.md.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_lib as hl  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

SUPPLIER = "Bloomstones"
DATE = "2026-08-26"
SOURCE_TAG = "Chad Gage, Bloomstones London \u2014 Smash file 2026-08-26"
_SCRATCH = (r"C:\Users\thefi\AppData\Local\Temp\claude"
            r"\C--Users-thefi-OneDrive---Finch-s-Stone---marble-Ltd-Claude-projects"
            r"\11376a96-79ec-4837-9bed-5fc6f837b660\scratchpad\bloom-zip")
DEFAULT_SRC = os.path.join(_SCRATCH, "All Quartz + Close Ups")
DEFAULT_ZIP = os.path.join(hl._HOME, "Downloads", "Quartz .zip")
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Bloomstone quartz")
UNMATCHED_DIR = os.path.join(DEST_ROOT, f"_unmatched from Chad {DATE}")
PLAN_JSON = os.path.join(hl.CACHE_ROOT, "bloomstones-chad", "plan.json")
REPORT_MD = os.path.join(hl.REPORTS_DIR, "bloomstones-chad-REPORT.md")
SHEET_MAINS = os.path.join(hl.REPORTS_DIR, "bloomstones-chad-mains.png")
SHEET_GALLERY = os.path.join(hl.REPORTS_DIR, "bloomstones-chad-galleries.png")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ""}
SKIP_EXT = {".mp4", ".mov", ".psd", ".pdf", ".docx", ".ds_store"}
RAW_SUBFOLDERS = {"\u5b9e\u7269\u56fe", "inside", "outside"}   # raw-camera dumps: OneDrive only
MAX_CLOSEUPS = 4

# folder / file-stem -> library colour (supplier Bloomstones, Quartz)
FOLDER_MAP = {
    "blanco white": "Bianco White",
    "aurora beige polished": "Aurora Beige",
    "viola leathered": "Viola",
    "viola polished": "Viola",
    "vagli leathered": "Vagli leathered",
    "perla gold honed": "Perla Gold",
    "calacutta gold": "Calacatta Gold",
    "bianco calacutta": "Bianco Calacatta",
    # Super Jumbos/ file stems
    "calacatta gold sj": "Calacatta Gold",
    "calacatta nile": "Calacatta Nile",
    "carrara gold": "Carrara Gold",
    "taj mahal": "Taj Mahal (Printed Quartz)",
    "taj velvelet": "Taj Velvet Cascade",
    "venus gold": "Venus Gold",
}
# per-file overrides keyed by rel path (forward slashes): kind | "skip"
FILE_OVERRIDES = {
    "Viola Leathered/Viola Leathered Full Slab.jpg": "room",        # it is a kitchen photo
    "Viola Leathered/Viola Leathrered Close up 1.JPG": "slab",     # byte-identical to Viola Polished Full Slab (5981x3197 slab face)
    "Aurora Beige Polished/TM Quartzite Collag..jpg": "skip",       # 698px collage of another range
    "Luxe Surfaces/Red Sparkle/Red Sparkle.jpg": "skip",           # 600x630 swatch
}
# main-image status override where the only slab shot is not a slab-face photo
MAIN_STATUS_OVERRIDE = {
    "Blue Sparkle": "closeup-only",   # 2576x2496 square crop is all Chad sent
}


def nrm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def classify(rel):
    """kind for a file: 'slab' | 'closeup' | 'room' | 'skip'."""
    if rel in FILE_OVERRIDES:
        return FILE_OVERRIDES[rel]
    parts = rel.split("/")
    if any(p in RAW_SUBFOLDERS for p in parts[:-1]):
        return "raw"
    stem = os.path.splitext(parts[-1])[0].lower()
    if "fitted" in stem:
        return "room"
    if re.search(r"c\s?lose\s?up", stem):
        return "closeup"
    if stem.startswith("img_"):
        return "closeup"
    return "slab"       # "Full Slab", bare colour name, DSC*, SJ stems


def inventory(src):
    items = []
    for dp, dn, fns in os.walk(src):
        dn[:] = [d for d in dn if not d.startswith("._")]
        for f in sorted(fns):
            if f.startswith("._") or f == ".DS_Store":
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in SKIP_EXT:
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, src).replace("\\", "/")
            if "/" not in rel:          # loose PDFs/docx/logos at top level
                continue
            try:
                with Image.open(p) as im:
                    w, h = im.size
                    fmt = im.format
            except Exception:
                continue
            sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
            items.append({"rel": rel, "path": p, "w": w, "h": h, "fmt": fmt, "sha": sha,
                          "bytes": os.path.getsize(p)})
    return items


def colour_key(rel):
    parts = rel.split("/")
    top = parts[0]
    if top == "Luxe Surfaces":
        parts = parts[1:]
    if parts[0] == "Super Jumbos":
        return os.path.splitext(parts[1])[0], "Super Jumbos/" + parts[1]
    return parts[0], parts[0]


def build_plan(src):
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == SUPPLIER and s.get("material") == "Quartz"]
    by_norm = {nrm(s["colour"]): s for s in entries}
    pb = hl.load_pricebook(SUPPLIER)
    pb_norm = {nrm(c): c for c in pb}

    items = inventory(src)
    seen_sha = {}
    groups = {}          # colour label (folder) -> {"entry":..., "files":[...]}
    for it in items:
        key, label = colour_key(it["rel"])
        it["kind"] = classify(it["rel"])
        it["label"] = label
        mapped = FOLDER_MAP.get(key.lower()) or FOLDER_MAP.get(key.lower().replace("calacutta", "calacatta"))
        ent = by_norm.get(nrm(mapped)) if mapped else by_norm.get(nrm(key)) or by_norm.get(nrm(key.replace("Calacutta", "Calacatta")))
        pbc = pb_norm.get(nrm(mapped or key))
        if ent is None and pbc:
            # price-book colour with no library entry yet -> create it (HARVEST-SPEC rule 4)
            eid = "bloomstones--" + re.sub(r"[^a-z0-9]+", "-", pbc.lower()).strip("-")
            info = pb[pbc]
            ent = {"id": eid, "supplier": SUPPLIER, "colour": pbc, "material": "Quartz",
                   "naturalStone": False, "illustrationOnly": False,
                   "thicknesses": sorted(info["thicknesses"]) or [20, 30], "productUrl": "",
                   "image": {"file": "", "status": "missing", "source": "", "borrowedFrom": ""},
                   "slabSizes": hl.format_slab_sizes(info["sizes"]) if info["sizes"] else "",
                   "details": "Bloomstones · Quartz · " + "/".join(sorted(info["finishes"])) + " · Luxe range (price book only, not on bloomstoneslondon.com)",
                   "_new": True}
            by_norm[nrm(pbc)] = ent
        gkey = ent["id"] if ent else "UNMATCHED:" + key
        g = groups.setdefault(gkey, {"entry": ent, "folders": set(), "files": [], "key": key, "pb": pbc})
        g["folders"].add(label)
        it["dup_of"] = seen_sha.get(it["sha"])
        if it["dup_of"] is None:
            seen_sha[it["sha"]] = it["rel"]
        g["files"].append(it)

    plan = {"groups": [], "unmatched": []}
    for gkey, g in sorted(groups.items(), key=lambda kv: kv[0]):
        ent = g["entry"]
        files = g["files"]
        rec = {"key": g["key"], "folders": sorted(g["folders"]), "files": files, "entry_id": ent["id"] if ent else None,
               "colour": ent["colour"] if ent else g["key"], "pb": g["pb"],
               "new_entry": {k: v for k, v in ent.items() if k != "_new"} if ent and ent.get("_new") else None,
               "created_by_chad": bool(ent and (ent.get("_new") or "price book only" in str(ent.get("details", ""))))}
        if not ent:
            plan["unmatched"].append(rec)
            continue
        cur = ent.get("image") or {}
        cur_src = cur.get("source", "") or ""
        main_replaceable = (cur.get("status") in ("missing", "representative", "closeup-only")
                            or bool(cur.get("borrowedFrom")) or cur_src.startswith(SOURCE_TAG)
                            or not cur.get("file"))
        usable = [f for f in files if f["kind"] in ("slab", "closeup", "room") and f["dup_of"] is None]
        slabs = [f for f in usable if f["kind"] == "slab"]

        def slab_score(f):
            ar = f["w"] / f["h"]
            band = 2 if 1.75 <= ar <= 2.3 else (1 if ar >= 1.4 else 0)
            return (band, f["w"] * f["h"])
        slabs.sort(key=slab_score, reverse=True)
        closeups = [f for f in usable if f["kind"] == "closeup"]
        rooms = [f for f in usable if f["kind"] == "room"]
        rec.update({
            "main_replaceable": main_replaceable,
            "current_status": ("chad-rerun (was missing)" if cur_src.startswith(SOURCE_TAG) else cur.get("status")),
            "current_source": cur_src[:60],
            "main": slabs[0]["rel"] if (main_replaceable and slabs) else None,
            "main_status": MAIN_STATUS_OVERRIDE.get(ent["colour"], "slab"),
            "alts": [f["rel"] for f in (slabs[1:] if (main_replaceable and slabs) else slabs)],
            "closeups": [f["rel"] for f in closeups[:MAX_CLOSEUPS]],
            "closeups_skipped": [f["rel"] for f in closeups[MAX_CLOSEUPS:]],
            "rooms": [f["rel"] for f in rooms],
            "raw": [f["rel"] for f in files if f["kind"] == "raw"],
            "dupes": [f["rel"] for f in files if f["dup_of"]],
        })
        plan["groups"].append(rec)
    plan["lib_generated"] = lib["generated"]
    return plan, lib


def print_report(plan):
    print(f"{'entry':40} {'cur':13} {'main?':6} {'alt':>3} {'cu':>3} {'rm':>3}  folders")
    for g in plan["groups"]:
        print(f"{g['entry_id'] + (' (NEW)' if g['new_entry'] else ''):40} {str(g['current_status']):13} "
              f"{'SET' if g['main'] else ('keep' if not g['main_replaceable'] else 'none'):6} "
              f"{len(g['alts']):3} {len(g['closeups']):3} {len(g['rooms']):3}  {', '.join(g['folders'])}")
    print("\nUNMATCHED (not a Bloomstones quartz entry):")
    for u in plan["unmatched"]:
        print(f"  {u['key']:24} pb={u['pb'] or '-':20} files={len(u['files'])}  {', '.join(u['folders'])}")


def copy_original(f, folder):
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(f["rel"])
    sub = os.path.dirname(f["rel"]).split("/")
    # keep raw-camera subfolder name, drop the colour/Luxe/Super Jumbos levels
    raw_sub = [s for s in sub if s in RAW_SUBFOLDERS]
    if raw_sub:
        folder = os.path.join(folder, raw_sub[-1])
        os.makedirs(folder, exist_ok=True)
    if not os.path.splitext(name)[1]:
        name += "." + (f["fmt"] or "jpg").lower().replace("jpeg", "jpg")
    dest = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', "_", name))
    if not os.path.exists(dest) or os.path.getsize(dest) != f["bytes"]:
        shutil.copy2(f["path"], dest)
    return dest


def apply(plan, src):
    files_by_rel = {f["rel"]: f for g in plan["groups"] + plan["unmatched"] for f in g["files"]}
    lib = hl.load_library()
    ids = {s["id"]: s for s in lib["slabs"]}
    writes = {}   # entry_id -> {"main": {...} | None, "gallery": [items]}
    sheet_mains, sheet_gallery = [], []

    for g in plan["groups"]:
        ent = ids.get(g["entry_id"]) or g["new_entry"]
        eid = ent["id"]
        folder = os.path.join(DEST_ROOT, hl._clean_folder_name(ent["colour"]))
        for f in g["files"]:               # every original (incl. raw dumps + dupes) to OneDrive
            copy_original(f, folder)
        existing = [im for im in (ent.get("images") or []) if not str(im.get("source", "")).startswith(SOURCE_TAG)]
        n_cu = sum(1 for im in existing if im.get("kind") == "closeup")
        n_rm = sum(1 for im in existing if im.get("kind") == "room")
        n_alt = sum(1 for im in existing if im.get("kind", "slab") == "slab" and im.get("file") != (ent.get("image") or {}).get("file"))
        gallery = []
        main = None
        if g["main"]:
            f = files_by_rel[g["main"]]
            fn = hl.to_library_webp(f["path"], eid)
            main = {"file": fn, "status": g["main_status"], "source": f"{SOURCE_TAG} ({f['rel']})", "borrowedFrom": ""}
            sheet_mains.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), g["main_status"]))
            print(f"MAIN  {eid} <- {f['rel']}", flush=True)
        for rel in g["alts"]:
            f = files_by_rel[rel]; n_alt += 1
            fn = hl.to_library_webp(f["path"], f"{eid}--alt{n_alt}")
            gallery.append({"file": fn, "status": "slab", "kind": "slab", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"slab alt{n_alt}"))
        for rel in g["closeups"]:
            f = files_by_rel[rel]; n_cu += 1
            fn = hl.to_library_webp(f["path"], f"{eid}--closeup{n_cu}")
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"closeup{n_cu}"))
        for rel in g["rooms"]:
            f = files_by_rel[rel]; n_rm += 1
            fn = hl.to_library_webp(f["path"], f"{eid}--room{n_rm}")
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"room{n_rm}"))
        aliases = sorted({fo.split("/")[-1].rsplit(".", 1)[0] if fo.startswith("Super Jumbos/") else fo
                          for fo in g["folders"]} - {ent["colour"]})
        writes[eid] = {"main": main, "gallery": gallery, "aliases": aliases}
        print(f"  {eid}: +{len(gallery)} gallery", flush=True)

    for u in plan["unmatched"]:
        folder = os.path.join(UNMATCHED_DIR, hl._clean_folder_name(u["key"]))
        for f in u["files"]:
            copy_original(f, folder)

    def mutate(lib):
        ids = {s["id"]: s for s in lib["slabs"]}
        counts = {"mains": 0, "alts": 0, "closeups": 0, "rooms": 0, "entries": 0, "new_entries": 0}
        for g in plan["groups"]:
            if g["new_entry"] and g["entry_id"] not in ids:
                lib["slabs"].append(json.loads(json.dumps(g["new_entry"])))
                ids[g["entry_id"]] = lib["slabs"][-1]
                counts["new_entries"] += 1
        for eid, w in writes.items():
            ent = ids[eid]
            counts["entries"] += 1
            imgs = [im for im in (ent.get("images") or []) if not str(im.get("source", "")).startswith(SOURCE_TAG)]
            if w["main"]:
                ent["image"] = w["main"]
                counts["mains"] += 1
                imgs = [im for im in imgs if im.get("kind", "slab") != "slab" or im.get("file") != w["main"]["file"]]
                imgs.insert(0, dict(w["main"], kind="slab"))
            elif ent.get("image", {}).get("file") and not any(im.get("file") == ent["image"]["file"] for im in imgs):
                imgs.insert(0, dict(ent["image"], kind="slab"))
            for it in w["gallery"]:
                imgs.append(it)
                counts["alts" if it["kind"] == "slab" else it["kind"] + "s"] += 1
            ent["images"] = imgs
            if w["aliases"]:
                ent["aliases"] = sorted(set(ent.get("aliases") or []) | set(w["aliases"]))
        return counts

    counts = hl.patch_library(mutate, supplier=SUPPLIER)
    if sheet_mains:
        hl.contact_sheet(sheet_mains, SHEET_MAINS, cols=8)
    if sheet_gallery:
        hl.contact_sheet(sheet_gallery, SHEET_GALLERY, cols=8)
    write_report(plan, counts)
    print(counts)
    return counts


def write_report(plan, counts):
    lib = hl.load_library()
    still = [s["colour"] for s in lib["slabs"] if s.get("supplier") == SUPPLIER and s.get("material") == "Quartz"
             and (s.get("image") or {}).get("status") != "slab"]
    mains = [g for g in plan["groups"] if g["main"]]
    kept = [g for g in plan["groups"] if not g["main_replaceable"]]
    lines = [f"# Bloomstones — Chad Gage photo zip import ({DATE})", "",
             "Source: `Quartz .zip` (1.9 GB) from Chad Gage, Bloomstones London — `All Quartz + Close Ups/<Colour>/`.",
             "Not a website harvest. Script: `tools/bloom_chad_import.py` (`--report` then `--apply`).", "",
             "## Counts",
             f"- Zip colour folders (after merging Luxe Surfaces duplicates + Super Jumbos stems): **{len(plan['groups']) + len(plan['unmatched'])}**",
             f"- Matched to Bloomstones quartz entries: **{len(plan['groups'])}** (incl. **{sum(1 for g in plan['groups'] if g['created_by_chad'])}** entries created for price-book colours with no entry: "
             + ", ".join(g['colour'] for g in plan['groups'] if g['created_by_chad']) + ")",
             f"- Mains set/replaced: **{counts['mains']}** — " + ", ".join(f"{g['colour']} ({g['current_status']}→{g['main_status']})" for g in mains),
             f"- Entries whose site main was kept (Chad slab shots added as `kind: slab` `--alt` images): **{len(kept)}**",
             f"- Extra slab images: **{counts['alts']}** · closeups: **{counts['closeups']}** · rooms: **{counts['rooms']}**",
             f"- Unmatched folders (in Chad's photos but not in our book): **{len(plan['unmatched'])}** — "
             + ", ".join(u["key"] for u in plan["unmatched"]),
             f"- Bloomstones quartz entries STILL without a `status: slab` main: **{len(still)}** — " + ", ".join(still), "",
             "## Kind classification",
             "`Full Slab` / bare colour-name / `DSC*` / Super-Jumbo stems = slab; `Close up N` / `IMG_*` = closeup; `Fitted` = room.",
             "Bare-name 4844x3229 (ar 1.5) files are slab-on-A-frame product shots — kept as `kind: slab` (viewed on a thumbnail sheet first).",
             "Raw-camera subfolders (实物图 / inside / outside) copied to OneDrive only, not the library. Dedupe by SHA-256 (Luxe Surfaces/ duplicates, Viola Polished ≡ Viola Leathered close-ups).",
             "Per-file overrides: " + "; ".join(f"`{k}` → {v}" for k, v in FILE_OVERRIDES.items()) + ".",
             "Main-status overrides: " + "; ".join(f"{k} → {v}" for k, v in MAIN_STATUS_OVERRIDE.items()) + ".", "",
             "## Name mapping (folder → library colour)",
             ", ".join(f"{k} → {v}" for k, v in FOLDER_MAP.items()), "",
             "## Notes / to ask Chad",
             "- `Calacatta Nile` is only a 555x416 PNG (Super Jumbos) — main set but low-res; ask for the full file.",
             "- `Blue Sparkle` is a 2576x2496 square crop — main set as `closeup-only`; ask for a full-slab shot.",
             "- `Viola Leathered Full Slab.jpg` is a kitchen photo (imported as room); `Viola Polished Full Slab` is the slab. The Viola entry's site main was kept.",
             "- Top-level `Calacatta Gold/` (DSC/IMG raw shots) and `Calacutta Gold/` and `Super Jumbos/CALACATTA GOLD SJ` all landed on the one quartz `Calacatta Gold` entry (price book has one quartz Calacatta Gold, 3500x2000 = SJ). If the T1 folder is a different standard-size product, it needs its own price-book row first.",
             "- `Super Jumbos/TAJ MAHAL` → `Taj Mahal (Printed Quartz)` (quartz; existing OneDrive main kept, SJ shot added as alt). LuxeStone `Taj Mahal` (still missing) may be the same product — not touched (other supplier string).",
             "- Unmatched folders were copied to OneDrive `Bloomstone quartz/_unmatched from Chad " + DATE + "/` only. Calacatta Supreme and Sorrento exist in the book for OTHER suppliers (Nile Stone/UK Stone Co; IQ/KSG) — not Bloomstones.",
             "- The zip holds AppleDouble stubs (`._Concreto Light`, `._Grigio Glitter`, `._Nero Glitter`, `._Nero Marquina`) with NO matching folder — those colours existed on Chad's Mac but were not included; Concreto Light is still `missing`. Ask Chad for them (Grigio/Nero Glitter, Nero Marquina are not in the book).",
             "- Two price-book Bloomstones colours had no library entry (Arabescato Storm, Valencia Gold — Luxe Jumbo rows) — entries created with Chad's photos as mains.",
             "- Site-harvest `scale` is not set on Chad's images (A-frame / hand-held shots; not true-scale).",
             f"- Closeups capped at {MAX_CLOSEUPS} new per entry; skipped: "
             + "; ".join(f"{g['colour']}: {len(g['closeups_skipped'])}" for g in plan["groups"] if g["closeups_skipped"]) + ".", "",
             "## Re-run",
             "```", "cd tools", "python bloom_chad_import.py --report", "python bloom_chad_import.py --apply   # idempotent; rebuilds Chad-sourced items", "```",
             f"Originals: OneDrive `1. QUARTZ\\Bloomstone quartz\\<Colour>\\`. Contact sheets: `{os.path.basename(SHEET_MAINS)}`, `{os.path.basename(SHEET_GALLERY)}`.",
             ]
    open(REPORT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("report:", REPORT_MD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--zip", default=DEFAULT_ZIP)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(a.src):
        if not os.path.exists(a.zip):
            sys.exit(f"no source folder {a.src} and no zip {a.zip}")
        dest = os.path.dirname(a.src)
        print("extracting", a.zip, "->", dest)
        with zipfile.ZipFile(a.zip) as z:
            for i in z.infolist():
                b = os.path.basename(i.filename)
                if i.is_dir() or b.startswith("._") or b == ".DS_Store":
                    continue
                z.extract(i, dest)
    plan, lib = build_plan(a.src)
    os.makedirs(os.path.dirname(PLAN_JSON), exist_ok=True)
    json.dump(plan, open(PLAN_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=list)
    print_report(plan)
    if a.apply:
        apply(plan, a.src)


if __name__ == "__main__":
    main()

"""Import Carl Kimpton's (Quantum Stone UK — the Picasso Surfaces distributor) Google Drive
photo pack into the slab library.

Source: Google Drive folder Carl sent 2026-09-10 in reply to Graham's 5 Sep "Picasso colours –
a few I can't find on the websites" email — one sub-folder per colour, ~51 folders (files dated
Mar/Apr 2026). Downloaded with `gdown.download_folder(...)` into a local folder; not a website
harvest, so no curl.

    python picasso_carl_import.py --src "<folder>" --report     # match/plan table, changes nothing
    python picasso_carl_import.py --src "<folder>" --apply      # copy originals -> OneDrive,
                                                                #   webps -> images/, patch slabs.json
                                                                #   (Picasso Surfaces only), sheets + report

Idempotent: every image this script writes carries `source` starting with SOURCE_TAG; on re-run
those gallery items are rebuilt from scratch and a main set by this script is re-evaluated.
Main rule (HARVEST-SPEC + bloom_chad_import precedent): a site main with `status: slab` is kept
and Carl's slab shots become extra `kind: slab` images (`{id}--altN.webp`) — EXCEPT where the
current main is a tiny web image (< MIN_MAIN_W px wide, e.g. the 750 px Mirror-series shots from
the old picassostones.com) and Carl sent a proper slab face: then Carl's shot becomes the main
("upgraded") and the old main is kept as an alt.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_lib as hl  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

SUPPLIER = "Picasso Surfaces"
DISTRIBUTOR = "Quantum Stone"
DATE = "2026-09-10"
SOURCE_TAG = "Carl Kimpton, Quantum Stone UK — Google Drive photo folder 2026-09-10"
DRIVE_URL = "https://drive.google.com/drive/folders/15pozW0r8SJF6TEbwkZnk3iKDvfotQwFC"
DEFAULT_SRC = os.path.join(hl._HOME, "Downloads", "Picasso from Carl 2026-09-10")
DEST_ROOT = os.path.join(hl.BRANDS_ROOT, "1. QUARTZ", "Quantum & Picasso Quartz")
SUBFOLDER = f"_from Carl {DATE}"
UNMATCHED_DIR = os.path.join(DEST_ROOT, f"_unmatched from Carl {DATE}")
PLAN_JSON = os.path.join(hl.CACHE_ROOT, "picasso-carl", "plan.json")
REPORT_MD = os.path.join(hl.REPORTS_DIR, "picasso-carl-REPORT.md")
SHEET_MAINS = os.path.join(hl.REPORTS_DIR, "picasso-carl-mains.png")
SHEET_GALLERY = os.path.join(hl.REPORTS_DIR, "picasso-carl-galleries.png")

LIB_EXT = {".jpg", ".jpeg", ".png", ".webp"}          # goes into the library (as webp)
COPY_ONLY_EXT = {".tif", ".tiff", ".bmp", ".heic"}    # OneDrive only
SKIP_EXT = {".mp4", ".mov", ".psd", ".pdf", ".docx", ".ds_store", ".ini"}
MAX_CLOSEUPS = 4
MAX_ROOMS = 4
MAX_ALTS = 3             # extra slab shots per colour (best aspect/size first, then rack shots)
MIN_MAIN_W = 1000        # current main narrower than this = "tiny web image", upgrade allowed

# Drive folder name -> price-book / library colour (Picasso Surfaces, Quartz)
FOLDER_MAP = {
    "arabescato creme matte": "Arabescato Creme",
    "arabescato crème polished": "Arabescato Creme",
    "arabescato creme polished": "Arabescato Creme",
    "royal cream polished": "Crema Royal",
    "royal creme matte": "Crema Royal",
    "snowdale (white shimmer)": "Snowdale",
    "taj onyx": "Taj Honey Onyx",
    "taj mahal extra matte": "Taj Mahal Extra",
    "taj mahal extra polished": "Taj Mahal Extra",
    "sunlight matte": "Sunlight",
    "white lake matte": "White Lake",
    "himalyan pink onyx": "Himalyan Pink Onyx",
    "himalayan pink onyx": "Himalyan Pink Onyx",
    "jade galcia": "Jade Glacia",
    # Carl's "Carrara Gold" folder holds files named "Calacatta Gold ..." (checked 2026-09-10):
    # the photos are Calacatta Gold. Carrara Gold itself gets nothing from this pack.
    "carrara gold": "Calacatta Gold",
}
# per-file overrides keyed by rel path (forward slashes): kind | "skip"
# (all viewed on the 2026-09-10 preview sheets — bare-name files that are kitchen renders)
FILE_OVERRIDES = {
    "Annapurna/Annapurna.JPEG": "room",
    "Cashmere/Cashmere (3).jpg": "room",
    "Cashmere/Cashmere (4).jpg": "room",
    "Cashmere/Cashmere (5).jpg": "room",
    "Cashmere/Cashmere (6).jpg": "room",
    "Cashmere/Cashmere (7).jpg": "room",
    "Cashmere/Cashmere racking.JPG": "rack",
    "Celestial Grey/Celestial Grey 1.jpg": "room",
    "Celestial Grey/Celestial Grey 2.jpg": "room",
    "Celestial White/Celestial White 1.jpg": "room",
    "Celestial White/Celestial White 2.jpg": "room",
    "Cristallo/Cristallo- (1).jpg": "room",          # backlit island render
    "Cristallo/Cristallo- (3).jpg": "room",
    "Orella/Orella (1).jpg": "room",
    "Patagonia/Patagonia  (1).JPEG": "room",         # backlit bedroom feature wall
    "Solarius/Solarius  (1).jpg": "room",
    "Viola/Viola  (1).jpeg": "closeup",              # tight crops of the slab face
    "Viola/Viola  (4).jpeg": "closeup",
    "Verde Onyx/Verde Onyx (2).jpg": "rack",         # backlit slab in the warehouse
}
# colour -> rel path that must be the main when the main is (re)set
MAIN_PICK = {
    "Viola": "Viola/fd0e26b84272509f57183d75ac6fd414.JPG",   # 8268 px slab face on a rack; the 2:1 ones are warehouse shots
}
# folders whose files are NOT slab faces even when the stem is bare
MAIN_STATUS_OVERRIDE = {}


def nrm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


_ROOM = re.compile(r"kitchen|install|island|worktop|countertop|fitted|bathroom|room|project|vanity|showroom|table|application", re.I)
_CLOSE = re.compile(r"detail|close|texture|zoom|swatch|macro", re.I)
# rack / A-frame / factory / back-lit shots: real slab photos but never a main (alt only)
_RACK = re.compile(r"rack|a-?frame|frame|factory|back\s?lit", re.I)
_SKIP = re.compile(r"\bLQ\b|low[- ]?res|thumb", re.I)


def classify(rel, w, h):
    """kind for a file: 'slab' | 'rack' | 'closeup' | 'room' | 'skip'.
    'rack' = slab on an A-frame / display stand: kept as kind:slab alt, never a main."""
    if rel in FILE_OVERRIDES:
        return FILE_OVERRIDES[rel]
    parts = rel.split("/")
    stem = os.path.splitext(parts[-1])[0]
    folders = " ".join(parts[:-1])
    if _SKIP.search(stem):
        return "skip"
    if _ROOM.search(folders) or _ROOM.search(stem):
        return "room"
    if _CLOSE.search(stem):
        return "closeup"
    if _RACK.search(stem):
        return "rack"
    if w and h and h > w * 1.1:          # portrait = hand-held / installed shot, not a slab face
        return "room"
    return "slab"


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
            if "/" not in rel:          # loose files at top level
                continue
            w = h = None
            fmt = None
            if ext in LIB_EXT or ext in COPY_ONLY_EXT:
                try:
                    with Image.open(p) as im:
                        w, h = im.size
                        fmt = im.format
                except Exception:
                    pass
            sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
            items.append({"rel": rel, "path": p, "w": w, "h": h, "fmt": fmt, "sha": sha,
                          "bytes": os.path.getsize(p), "ext": ext,
                          "lib_ok": ext in LIB_EXT and bool(w)})
    return items


def colour_key(rel):
    return rel.split("/")[0]


def build_plan(src):
    lib = hl.load_library()
    entries = [s for s in lib["slabs"] if s.get("supplier") == SUPPLIER]
    by_norm = {nrm(s["colour"]): s for s in entries}
    for s in entries:
        for a in s.get("aliases") or []:
            by_norm.setdefault(nrm(a), s)
    pb = hl.load_pricebook(SUPPLIER)
    pb_norm = {nrm(c): c for c in pb}

    items = inventory(src)
    seen_sha = {}
    groups = {}
    for it in items:
        key = colour_key(it["rel"])
        it["kind"] = classify(it["rel"], it["w"], it["h"]) if it["lib_ok"] else ("copy-only" if it["ext"] in COPY_ONLY_EXT else "skip")
        mapped = FOLDER_MAP.get(key.lower())
        ent = by_norm.get(nrm(mapped)) if mapped else by_norm.get(nrm(key))
        pbc = pb_norm.get(nrm(mapped or key))
        gkey = ent["id"] if ent else "UNMATCHED:" + key
        g = groups.setdefault(gkey, {"entry": ent, "folders": set(), "files": [], "key": key, "pb": pbc})
        g["folders"].add(key)
        it["dup_of"] = seen_sha.get(it["sha"])
        if it["dup_of"] is None:
            seen_sha[it["sha"]] = it["rel"]
        g["files"].append(it)

    plan = {"groups": [], "unmatched": []}
    for gkey, g in sorted(groups.items(), key=lambda kv: kv[0]):
        ent = g["entry"]
        files = g["files"]
        rec = {"key": g["key"], "folders": sorted(g["folders"]), "files": files,
               "entry_id": ent["id"] if ent else None,
               "colour": ent["colour"] if ent else g["key"], "pb": g["pb"]}
        if not ent:
            plan["unmatched"].append(rec)
            continue
        cur = ent.get("image") or {}
        cur_src = cur.get("source", "") or ""
        cur_w = 0
        if cur.get("file") and os.path.exists(os.path.join(hl.IMAGES_DIR, cur["file"])):
            try:
                with Image.open(os.path.join(hl.IMAGES_DIR, cur["file"])) as im:
                    cur_w = im.width
            except Exception:
                pass
        tiny = bool(cur.get("file")) and 0 < cur_w < MIN_MAIN_W
        main_replaceable = (cur.get("status") in ("missing", "representative", "closeup-only")
                            or bool(cur.get("borrowedFrom")) or cur_src.startswith(SOURCE_TAG)
                            or not cur.get("file") or tiny)
        usable = [f for f in files if f["kind"] in ("slab", "rack", "closeup", "room") and f["dup_of"] is None]
        slabs = [f for f in usable if f["kind"] == "slab"]

        def slab_score(f):
            ar = f["w"] / f["h"]
            band = 2 if 1.75 <= ar <= 2.3 else (1 if ar >= 1.4 else 0)
            return (band, f["w"] * f["h"])
        slabs.sort(key=slab_score, reverse=True)
        pick = MAIN_PICK.get(ent["colour"])
        if pick:
            slabs.sort(key=lambda f: f["rel"] != pick)      # stable: the pick moves to the front
        racks = [f for f in usable if f["kind"] == "rack"]
        closeups = [f for f in usable if f["kind"] == "closeup"]
        rooms = [f for f in usable if f["kind"] == "room"]
        set_main = bool(main_replaceable and slabs)
        rec.update({
            "main_replaceable": main_replaceable,
            "upgrade": bool(tiny and slabs and not cur_src.startswith(SOURCE_TAG)),
            "current_status": ("carl-rerun" if cur_src.startswith(SOURCE_TAG) else cur.get("status")),
            "current_w": cur_w,
            "current_source": cur_src[:60],
            "main": slabs[0]["rel"] if set_main else None,
            "main_status": MAIN_STATUS_OVERRIDE.get(ent["colour"], "slab"),
            "alts": ([f["rel"] for f in (slabs[1:] if set_main else slabs)] + [f["rel"] for f in racks])[:MAX_ALTS],
            "closeups": [f["rel"] for f in closeups[:MAX_CLOSEUPS]],
            "closeups_skipped": [f["rel"] for f in closeups[MAX_CLOSEUPS:]],
            "rooms": [f["rel"] for f in rooms[:MAX_ROOMS]],
            "rooms_skipped": [f["rel"] for f in rooms[MAX_ROOMS:]],
            "copy_only": [f["rel"] for f in files if f["kind"] == "copy-only"],
            "skipped": [f["rel"] for f in files if f["kind"] == "skip"],
            "dupes": [f["rel"] for f in files if f["dup_of"]],
        })
        plan["groups"].append(rec)
    plan["lib_generated"] = lib["generated"]
    return plan, lib


def print_report(plan):
    print(f"{'entry':40} {'cur':13} {'curW':>5} {'main?':8} {'alt':>3} {'cu':>3} {'rm':>3}  folders")
    for g in plan["groups"]:
        act = "UPGRADE" if g["upgrade"] else ("SET" if g["main"] else ("keep" if not g["main_replaceable"] else "none"))
        print(f"{g['entry_id']:40} {str(g['current_status']):13} {g['current_w']:5} {act:8} "
              f"{len(g['alts']):3} {len(g['closeups']):3} {len(g['rooms']):3}  {', '.join(g['folders'])}")
    print("\nUNMATCHED (not a Picasso Surfaces entry):")
    for u in plan["unmatched"]:
        print(f"  {u['key']:36} pb={u['pb'] or '-':20} files={len(u['files'])}")
    print("\nFILE KINDS:")
    for g in plan["groups"] + plan["unmatched"]:
        for f in g["files"]:
            dup = f" (dup of {f['dup_of']})" if f.get("dup_of") else ""
            print(f"  {f['kind']:9} {f['w']}x{f['h']}  {f['rel']}{dup}")


def free_slot(eid, kind, n, mine):
    """Next gallery number for `{eid}--{kind}{n}` that does not clobber a file on disk
    (unless that file is one this script wrote — listed in `mine`). Never overwrite."""
    while True:
        fn = f"{eid}--{kind}{n}.webp"
        if fn in mine or not os.path.exists(os.path.join(hl.IMAGES_DIR, fn)):
            return n, fn[:-5]
        n += 1


def copy_original(f, folder):
    os.makedirs(folder, exist_ok=True)
    parts = f["rel"].split("/")
    name = parts[-1]
    sub = parts[1:-1]                      # keep sub-folders (e.g. "ARCTIC STORM INSTALL")
    if sub:
        folder = os.path.join(folder, *[re.sub(r'[<>:"/\\|?*]', "_", s) for s in sub])
        os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', "_", name.strip()))
    if not os.path.exists(dest) or os.path.getsize(dest) != f["bytes"]:
        shutil.copy2(f["path"], dest)
    return dest


def apply(plan, src):
    files_by_rel = {f["rel"]: f for g in plan["groups"] + plan["unmatched"] for f in g["files"]}
    lib = hl.load_library()
    ids = {s["id"]: s for s in lib["slabs"]}
    writes = {}
    sheet_mains, sheet_gallery = [], []

    for g in plan["groups"]:
        ent = ids[g["entry_id"]]
        eid = ent["id"]
        folder = os.path.join(DEST_ROOT, hl._clean_folder_name(ent["colour"]), SUBFOLDER)
        for f in g["files"]:               # every original (incl. tif + dupes + LQ) to OneDrive
            copy_original(f, folder)
        existing = [im for im in (ent.get("images") or []) if not str(im.get("source", "")).startswith(SOURCE_TAG)]
        n_cu = sum(1 for im in existing if im.get("kind") == "closeup")
        n_rm = sum(1 for im in existing if im.get("kind") == "room")
        n_alt = sum(1 for im in existing if im.get("kind", "slab") == "slab" and im.get("file") != (ent.get("image") or {}).get("file"))
        gallery = []
        main = None
        if g["main"]:
            f = files_by_rel[g["main"]]
            fn = hl.to_library_webp(f["path"], eid + ("--carl" if g["upgrade"] else ""))
            main = {"file": fn, "status": g["main_status"], "source": f"{SOURCE_TAG} ({f['rel']})", "borrowedFrom": ""}
            sheet_mains.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), "UPGRADE" if g["upgrade"] else g["main_status"]))
            print(f"MAIN  {eid} <- {f['rel']}" + ("  [upgrade]" if g["upgrade"] else ""), flush=True)
        # files a previous run of THIS script wrote for this entry may be reused; anything else on disk is never overwritten
        mine = {im.get("file") for im in (ent.get("images") or []) if str(im.get("source", "")).startswith(SOURCE_TAG)}
        for rel in g["alts"]:
            f = files_by_rel[rel]
            n_alt, base = free_slot(eid, "alt", n_alt + 1, mine)
            fn = hl.to_library_webp(f["path"], base)
            gallery.append({"file": fn, "status": "slab", "kind": "slab", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"slab alt{n_alt}" + (" rack" if f["kind"] == "rack" else "")))
        for rel in g["closeups"]:
            f = files_by_rel[rel]
            n_cu, base = free_slot(eid, "closeup", n_cu + 1, mine)
            fn = hl.to_library_webp(f["path"], base)
            gallery.append({"file": fn, "status": "closeup", "kind": "closeup", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"closeup{n_cu}"))
        for rel in g["rooms"]:
            f = files_by_rel[rel]
            n_rm, base = free_slot(eid, "room", n_rm + 1, mine)
            fn = hl.to_library_webp(f["path"], base)
            gallery.append({"file": fn, "status": "representative", "kind": "room", "source": f"{SOURCE_TAG} ({rel})", "borrowedFrom": ""})
            sheet_gallery.append((ent["colour"], os.path.join(hl.IMAGES_DIR, fn), f"room{n_rm}"))
        aliases = sorted(set(g["folders"]) - {ent["colour"]} - {"Carrara Gold"})
        writes[eid] = {"main": main, "gallery": gallery, "aliases": aliases, "upgrade": g["upgrade"]}
        print(f"  {eid}: +{len(gallery)} gallery", flush=True)

    for u in plan["unmatched"]:
        folder = os.path.join(UNMATCHED_DIR, hl._clean_folder_name(u["key"]))
        for f in u["files"]:
            copy_original(f, folder)

    def mutate(lib):
        ids = {s["id"]: s for s in lib["slabs"]}
        counts = {"mains": 0, "upgrades": 0, "alts": 0, "closeups": 0, "rooms": 0, "entries": 0}
        for eid, w in writes.items():
            ent = ids[eid]
            counts["entries"] += 1
            imgs = [im for im in (ent.get("images") or []) if not str(im.get("source", "")).startswith(SOURCE_TAG)]
            old_main = ent.get("image") or {}
            if w["main"]:
                ent["image"] = w["main"]
                counts["mains"] += 1
                if w["upgrade"]:
                    counts["upgrades"] += 1
                imgs = [im for im in imgs if im.get("file") != w["main"]["file"]]
                imgs.insert(0, dict(w["main"], kind="slab"))
                # keep the old (small) site main as an alt so nothing is lost
                if w["upgrade"] and old_main.get("file") and not any(im.get("file") == old_main["file"] for im in imgs):
                    imgs.insert(1, dict(old_main, kind="slab"))
            elif old_main.get("file") and not any(im.get("file") == old_main["file"] for im in imgs):
                imgs.insert(0, dict(old_main, kind="slab"))
            for it in w["gallery"]:
                imgs.append(it)
                counts["alts" if it["kind"] == "slab" else it["kind"] + "s"] += 1
            ent["images"] = imgs
            if w["aliases"]:
                ent["aliases"] = sorted(set(ent.get("aliases") or []) | set(w["aliases"]))
            sups = list(ent.get("suppliers") or [])
            if DISTRIBUTOR not in sups:
                sups.append(DISTRIBUTOR)
            ent["suppliers"] = sups
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
    still = [s["colour"] for s in lib["slabs"] if s.get("supplier") == SUPPLIER
             and (s.get("image") or {}).get("status") != "slab"]
    mains = [g for g in plan["groups"] if g["main"]]
    kept = [g for g in plan["groups"] if not g["main_replaceable"]]
    lines = [f"# Picasso Surfaces — Carl Kimpton (Quantum Stone) Google Drive photo pack import ({DATE})", "",
             f"Source: Carl's Drive folder {DRIVE_URL} (one sub-folder per colour, files dated Mar/Apr 2026), sent 2026-09-10",
             "in reply to Graham's 5 Sep email. Downloaded with gdown; not a website harvest.",
             "Script: `tools/picasso_carl_import.py --src <folder> --report` then `--apply`.", "",
             "## Counts",
             f"- Drive colour folders: **{len(plan['groups']) + len(plan['unmatched'])}** (matched to Picasso entries: **{len(plan['groups'])}**, unmatched: **{len(plan['unmatched'])}**)",
             f"- Mains set/replaced: **{counts['mains']}** (of which UPGRADED from a tiny web image: **{counts['upgrades']}**) — "
             + ", ".join(f"{g['colour']} ({g['current_status']} {g['current_w']}px→{'upgrade' if g['upgrade'] else g['main_status']})" for g in mains),
             f"- Entries whose site main was kept (Carl's slab shots added as `kind: slab` `--alt` images): **{len(kept)}**",
             f"- Extra slab images: **{counts['alts']}** · closeups: **{counts['closeups']}** · rooms: **{counts['rooms']}**",
             f"- Unmatched folders (in Carl's pack but not a Picasso price-book colour): **{len(plan['unmatched'])}** — "
             + ", ".join(u["key"] for u in plan["unmatched"]),
             f"- Picasso entries STILL without a `status: slab` main: **{len(still)}** — " + ", ".join(still), "",
             "## Kind classification",
             "bare colour-name / `HQ` / `(2)` stems = slab (main candidate); `rack` / `on rack` = slab on an A-frame (kind: slab alt, never a main);",
             "`Detail` / `Close` = closeup; `Kitchen` / `install` / `Island` / `worktop` / `countertop` / an `INSTALL` sub-folder / portrait aspect = room;",
             "`LQ` = skipped (low-res duplicate); `.tif` = OneDrive only. Dedupe by SHA-256 (the two Arabescato Creme folders share one rack shot).",
             f"Main upgrade rule: current main < {MIN_MAIN_W} px wide AND Carl sent a slab face → Carl's becomes the main, the old one stays as an alt.",
             "Per-file overrides: " + ("; ".join(f"`{k}` → {v}" for k, v in FILE_OVERRIDES.items()) or "none") + ".", "",
             "## Name mapping (Drive folder → library colour)",
             ", ".join(f"{k} → {v}" for k, v in FOLDER_MAP.items()), "",
             "## Notes / to ask Carl (draft reply already in Graham's Outlook Drafts, 2026-09-10)",
             "- Carl's `Carrara Gold/` folder holds files named `Calacatta Gold ...` — imported to **Calacatta Gold**; Carrara Gold got nothing. Ask for a Carrara Gold slab shot.",
             "- **Verde Tempesta** (price book spells it `Verde Tempsta`): Carl — \"photos will be available soon, this isn't due to arrive until November\" (2026). Still `missing`; not discontinued.",
             "- **Viola**: 5 photos in the pack (main set from the 8268 px slab face) but NOT in the 2026 brochure — availability asked.",
             "- **White Mirror / Grey Mirror**: one photo each in the pack AND in the 2026 brochure (OneDrive `North Picasso Surfaces Brochure 2026.pdf`) — current; both 750 px old-site mains upgraded.",
             "- **Black Mirror / Calacatta Gold**: their Drive folders are EMPTY (Calacatta Gold's photos sit in the `Carrara Gold/` folder); neither is in the 2026 brochure, nor is Carrara Gold — photos + availability asked. Black Mirror keeps its 750 px old-site main.",
             "- **Silver Cloud**: in the pack + brochure, not in the price book — copied to `_unmatched` only.",
             "- **Symphony HD Print** (Taj Mahal / Ice Age / Water shadow / Winter field): in the pack + 2026 brochure, NOT in the price book → copied to `_unmatched` only; price band + slab size asked.",
             "- Site-harvest `scale` is not set on Carl's images (studio / A-frame shots; not true-scale).",
             f"- Closeups capped at {MAX_CLOSEUPS}, rooms at {MAX_ROOMS} new per entry; skipped: "
             + ("; ".join(f"{g['colour']}: {len(g['closeups_skipped'])} cu / {len(g['rooms_skipped'])} rm" for g in plan["groups"] if g["closeups_skipped"] or g["rooms_skipped"]) or "none") + ".", "",
             "## Re-run",
             "```", "cd tools", f"python picasso_carl_import.py --src \"<downloaded folder>\" --report",
             f"python picasso_carl_import.py --src \"<downloaded folder>\" --apply   # idempotent; rebuilds Carl-sourced items", "```",
             f"Originals: OneDrive `1. QUARTZ\\Quantum & Picasso Quartz\\<Colour>\\{SUBFOLDER}\\`. Contact sheets: `{os.path.basename(SHEET_MAINS)}`, `{os.path.basename(SHEET_GALLERY)}`.",
             ]
    os.makedirs(hl.REPORTS_DIR, exist_ok=True)
    open(REPORT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("report:", REPORT_MD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(a.src):
        sys.exit(f"no source folder {a.src}")
    plan, _ = build_plan(a.src)
    os.makedirs(os.path.dirname(PLAN_JSON), exist_ok=True)
    json.dump(plan, open(PLAN_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    if a.report or not a.apply:
        print_report(plan)
    if a.apply:
        apply(plan, a.src)


if __name__ == "__main__":
    main()

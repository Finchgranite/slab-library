"""Shared helpers for slab-library supplier harvest agents (phase 2, 2026-08-24).
Generalised from compac_harvest.py/compac_reconcile.py, clay_harvest.py/clay_reconcile.py,
akg_wp_sweep.py, bloom_harvest.py. Keep dependency-light: PIL + stdlib only.

Usage:
    import harvest_lib as hl
    html = hl.fetch(url, supplier="caesarstone", cache_key="4011-cloudburst").decode("utf-8", "replace")
    imgs = hl.extract_images(html, url)
    for im in imgs:
        kind = hl.classify_kind(im["url"], im["alt"], im["context"], im["width"], im["height"])
    entry, score = hl.match_colour(site_name, [(r["colour"], r) for r in entries])
    path = hl.save_original(data, DEST_ROOT, "Airy Concrete", "4044_full.jpg")
    fn = hl.to_library_webp(path, "caesarstone--airy-concrete")
    hl.contact_sheet([("Airy Concrete", path1), ("Snow", path2)], out_png, cols=8)
    lib = hl.load_library(); ...mutate...; hl.save_library(lib)   # bumps `generated`
    pb = hl.load_pricebook("Caesarstone")   # {colour: {thicknesses:set, finishes:set, sizes:{20:'3050x1440'}}}
Run any harvester with --report first (prints a match table, changes nothing), then --apply.
"""
import csv
import difflib
import html as H
import json
import os
import re
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Paths resolve on EITHER PC (home: C:\Users\thefi\<repo>; works: C:\Users\graha\projects\<repo>).
# The library root is wherever this file lives; the other two are searched under the user
# profile. Override with env vars SLAB_LIB_ROOT / SLAB_PRICEBOOK_CSV / SLAB_BRANDS_ROOT.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_HOME = os.environ.get("USERPROFILE") or os.path.expanduser("~")


def _first_existing(candidates, fallback):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return fallback


LIB_ROOT = os.environ.get("SLAB_LIB_ROOT") or os.path.dirname(TOOLS_DIR)
SLABS_JSON = os.path.join(LIB_ROOT, "slabs.json")
IMAGES_DIR = os.path.join(LIB_ROOT, "images")
PRICEBOOK_CSV = _first_existing(
    [os.environ.get("SLAB_PRICEBOOK_CSV"),
     os.path.join(_HOME, "stone-worktop-quotes", "materials", "supplier-price-book.csv"),
     os.path.join(_HOME, "projects", "stone-worktop-quotes", "materials", "supplier-price-book.csv")],
    r"C:\Users\thefi\stone-worktop-quotes\materials\supplier-price-book.csv")
BRANDS_ROOT = _first_existing(
    [os.environ.get("SLAB_BRANDS_ROOT"),
     os.path.join(_HOME, "OneDrive - Finch's Stone & marble Ltd", "Brands -Slabs -Kitchens-Website")],
    r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website")
CACHE_ROOT = os.path.join(TOOLS_DIR, "_cache")
REPORTS_DIR = os.path.join(TOOLS_DIR, "_reports")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

os.makedirs(CACHE_ROOT, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# ---------------------------------------------------------------- fetching --
def _safe_key(k):
    return re.sub(r'[<>:"/\\|?*]', "_", k)[:180]


def fetch(url, supplier=None, cache_key=None, tries=4, delay=15, binary=False,
          polite_delay=2.0, headers=None):
    """curl subprocess fetch (never python urllib -- several suppliers 429 it).
    Retries with exponential backoff on failure. If supplier+cache_key given,
    caches the raw bytes under tools/_cache/<supplier>/<cache_key>.{html,bin}
    and skips the network entirely on a cache hit. Returns bytes."""
    cache_path = None
    if supplier and cache_key:
        d = os.path.join(CACHE_ROOT, supplier)
        os.makedirs(d, exist_ok=True)
        cache_path = os.path.join(d, _safe_key(cache_key) + (".bin" if binary else ".html"))
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return open(cache_path, "rb").read()
    ua = (headers or {}).get("User-Agent", UA)
    d_ = delay
    last_err = None
    for i in range(tries):
        cmd = ["curl", "-sL", "--fail-with-body", "-A", ua, "--max-time", "90"]
        for k, v in (headers or {}).items():
            if k.lower() != "user-agent":
                cmd += ["-H", f"{k}: {v}"]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and r.stdout:
            if cache_path:
                open(cache_path, "wb").write(r.stdout)
            if polite_delay:
                time.sleep(polite_delay)
            return r.stdout
        last_err = f"rc={r.returncode} stderr={r.stderr[:200]!r}"
        if i < tries - 1:
            print(f"  retry {url[-70:]} ({last_err}) waiting {d_}s", flush=True)
            time.sleep(d_)
            d_ = min(d_ * 2, 120)
    raise RuntimeError(f"fetch failed for {url}: {last_err}")


def fetch_text(url, supplier=None, cache_key=None, **kw):
    return fetch(url, supplier=supplier, cache_key=cache_key, **kw).decode("utf-8", "replace")


def original_candidates(url):
    """A page's <img>/data-src often only references a WP-generated -WxH or
    -scaled thumbnail, but the true original upload commonly still exists on
    the server at the un-suffixed filename. Returns candidate URLs to try in
    order: [stripped-original, ...-scaled-stripped, as-given]."""
    base, _, fn = url.rpartition("/")
    cands = []
    stripped = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
    if stripped != fn:
        cands.append(f"{base}/{stripped}")
    if "-scaled." in fn:
        cands.append(f"{base}/{fn.replace('-scaled.', '.')}")
    cands.append(url)
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def fetch_best(url, supplier=None, cache_key=None, **kw):
    """Try original_candidates(url) in order (1 attempt each, no backoff
    spam), return (bytes, url_used) from the first that succeeds. Falls back
    to a full-retry fetch of the given url if every candidate 404s."""
    cands = original_candidates(url)
    quick_kw = dict(kw)
    quick_kw.setdefault("tries", 1)
    quick_kw.setdefault("polite_delay", 1.0)
    for i, c in enumerate(cands):
        ck = f"{cache_key}__c{i}" if cache_key else None
        try:
            return fetch(c, supplier=supplier, cache_key=ck, binary=True, **quick_kw), c
        except Exception:
            continue
    data = fetch(url, supplier=supplier, cache_key=cache_key, binary=True, **kw)
    return data, url


# ------------------------------------------------------------- image scrape --
_IMG_EXT = r'(?:jpe?g|png|webp|gif)'
_TINY_HINTS = re.compile(r'logo|icon|favicon|sprite|placeholder|spinner|loader|\.svg|flag-|qr[-_]?code', re.I)


def _strip_size_suffix(fn):
    fn = re.sub(r'-scaled(?=\.[a-zA-Z0-9]+$)', '', fn)
    fn = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', fn)
    return fn


def _attr(attrs, name):
    m = re.search(name + r'\s*=\s*"([^"]*)"', attrs) or re.search(name + r"\s*=\s*'([^']*)'", attrs)
    return H.unescape(m.group(1)) if m else None


def _int_attr(attrs, name):
    v = _attr(attrs, name)
    if not v:
        return None
    v = re.sub(r'[^0-9]', '', v)
    return int(v) if v else None


def _best_srcset(srcset):
    best_u, best_w = None, -1
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.rsplit(" ", 1)
        u = bits[0].strip()
        w = 0
        if len(bits) > 1:
            wm = re.match(r'(\d+)w', bits[1])
            if wm:
                w = int(wm.group(1))
        if w >= best_w:
            best_w, best_u = w, u
    return best_u


def _absolutize(u, base_url):
    u = H.unescape(u.strip().rstrip("\\'\""))
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return urllib.parse.urljoin(base_url, u)
    return u


def extract_images(html_text, base_url):
    """Every <img>/<source srcset>/og:image/twitter:image/CSS background-image
    in the page. De-dupes an original over its -WxH/-scaled scaled variants
    (same base filename -> keeps the biggest). Skips tiny/logo/svg/flag assets.
    Returns [{url, alt, context, width, height}, ...]."""
    out = {}

    def add(u, alt="", context="", w=None, h=None):
        if not u or u.startswith("data:"):
            return
        u = _absolutize(u, base_url)
        if not re.search(r'\.' + _IMG_EXT + r'(?:[?#]|$)', u, re.I):
            return
        if _TINY_HINTS.search(u):
            return
        fn = u.split("/")[-1].split("?")[0]
        base = _strip_size_suffix(fn)
        rank = 0
        if re.search(r'-scaled\.', fn, re.I):
            rank = 1
        elif not re.search(r'-\d+x\d+\.', fn, re.I):
            rank = 2
        key = base
        prev = out.get(key)
        cand = {"url": u, "alt": alt or "", "context": context, "width": w, "height": h, "_rank": rank}
        if prev is None or rank > prev["_rank"] or (rank == prev["_rank"] and (w or 0) > (prev["width"] or 0)):
            out[key] = cand

    for m in re.finditer(r'<img\b([^>]*)>', html_text, re.I):
        attrs = m.group(1)
        alt = _attr(attrs, "alt") or ""
        w = _int_attr(attrs, "width")
        h = _int_attr(attrs, "height")
        cls = _attr(attrs, "class") or ""
        for a in ("data-src", "data-lazy-src", "data-original", "src"):
            u = _attr(attrs, a)
            if u:
                add(u, alt, cls, w, h)
        srcset = _attr(attrs, "data-srcset") or _attr(attrs, "srcset")
        if srcset:
            best = _best_srcset(srcset)
            if best:
                add(best, alt, cls)

    for m in re.finditer(r'<source\b([^>]*)>', html_text, re.I):
        attrs = m.group(1)
        srcset = _attr(attrs, "data-srcset") or _attr(attrs, "srcset")
        if srcset:
            best = _best_srcset(srcset)
            if best:
                add(best, "", "source-srcset")

    for m in re.finditer(
            r'<meta[^>]+(?:property|name)="(?:og:image|twitter:image)"[^>]+content="([^"]+)"',
            html_text, re.I):
        add(m.group(1), "", "meta-image")

    for m in re.finditer(r'background-image\s*:\s*url\((["\']?)(.*?)\1\)', html_text, re.I):
        add(m.group(2), "", "css-background")

    return [v for v in out.values()]


# ---------------------------------------------------------------- classify --
_SLAB_HINTS = re.compile(r'\bslab\b|plaka|tablero|full[-_ ]?slab|\bfull\b', re.I)
_CLOSEUP_HINTS = re.compile(r'detail|close[-_ ]?up|\bcu\b|texture|zoom|swatch', re.I)
_ROOM_HINTS = re.compile(
    r'kitchen|bathroom|\broom\b|ambient|inspiration|application|project|install|vanity|interior|lifestyle',
    re.I)


def classify_kind(url, alt="", context="", width=None, height=None):
    """'slab' | 'closeup' | 'room' | None. Filename/alt/section hints first
    (per HARVEST-SPEC.md), then aspect ratio (~1.8-2.3:1 slab, ~1:1 closeup)."""
    hay = " ".join(str(x) for x in (url, alt, context) if x).lower()
    if _ROOM_HINTS.search(hay):
        return "room"
    if _CLOSEUP_HINTS.search(hay):
        return "closeup"
    if _SLAB_HINTS.search(hay):
        return "slab"
    if width and height:
        ar = width / height if height else 0
        ar_n = max(ar, 1 / ar) if ar else 0
        if 1.8 <= ar_n <= 2.3:
            return "slab"
        if 0.8 <= ar_n <= 1.25:
            return "closeup"
    return None


# ------------------------------------------------------------- name match --
_QUIRK_TOKEN_MAP = {
    "grey": "gray", "greys": "grays",
    "aegan": "aegean",
    "extra": "", "tm": "", "r": "",
}
_DROP_TOKENS = {"", "the", "collection", "range", "worktop", "worktops", "quartz",
                "porcelain", "fusion", "sintered", "surfaces", "icon"}


def norm(s):
    s = (s or "").replace("\u2122", "").replace("\u00ae", "")
    return re.sub(r'[^a-z0-9 ]', ' ', s.lower())


def _toks(s):
    out = set()
    for w in norm(s).split():
        w = _QUIRK_TOKEN_MAP.get(w, w)
        if w in _DROP_TOKENS:
            continue
        out.add(w)
    return out


def _fuzzy_subset(a, b):
    for t in a:
        if t not in b and not difflib.get_close_matches(t, list(b), n=1, cutoff=0.82):
            return False
    return True


def match_colour(site_name, candidates):
    """Token-subset matcher, both directions, tie-broken by SequenceMatcher
    ratio. candidates: iterable of (name, obj). Returns (obj_or_None, score)
    where score is (matched_token_count, ratio) -- (0, 0.0) on no match."""
    st = _toks(site_name)
    best, best_score = None, (0, 0.0)
    if not st:
        return None, best_score
    for name, obj in candidates:
        ct = _toks(name)
        if not ct:
            continue
        if _fuzzy_subset(ct, st) and _fuzzy_subset(st, ct):
            ratio = difflib.SequenceMatcher(None, site_name.lower(), str(name).lower()).ratio()
            score = (len(ct), ratio)
            if score > best_score:
                best, best_score = obj, score
    return best, best_score


# --------------------------------------------------------------- storage --
def _clean_folder_name(s):
    return re.sub(r'[<>:"/\\|?*]', "", s).strip()


def save_original(data, dest_root, colour, filename):
    """Write raw bytes into <dest_root>/<colour>/<filename> (creates the
    folder). Skips the write if the file already exists (idempotent). Returns
    the full path."""
    folder = os.path.join(dest_root, _clean_folder_name(colour))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', "_", filename))
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        open(path, "wb").write(data)
    return path


def to_library_webp(path_or_bytes, out_id, max_w=1600, quality=85):
    """Convert an original (path or raw bytes) into images/<out_id>.webp,
    max_w wide, RGB (flattens transparency onto white). Returns the filename
    (not the full path) for use as an `image.file`/`images[].file` value."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        im = Image.open(BytesIO(path_or_bytes))
    else:
        im = Image.open(path_or_bytes)
    if im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
    fn = out_id if out_id.lower().endswith(".webp") else out_id + ".webp"
    os.makedirs(IMAGES_DIR, exist_ok=True)
    im.save(os.path.join(IMAGES_DIR, fn), "WEBP", quality=quality)
    return fn


# ------------------------------------------------------------ contact sheet --
def contact_sheet(entries, out_png, cols=8, cell_w=200, cell_h=150, label_h=32):
    """entries: [(label, image_path_or_None), ...] or [(label, path, sublabel), ...].
    Labelled grid, `cols` per row. Writes out_png (and out_png with _2/_3...
    suffix if it would exceed ~64 rows, to keep file size sane)."""
    try:
        from PIL import ImageDraw, ImageFont
        font = ImageFont.load_default()
    except Exception:
        ImageDraw = None
        font = None

    MAX_ROWS_PER_SHEET = 20
    per_sheet = cols * MAX_ROWS_PER_SHEET
    base, ext = os.path.splitext(out_png)
    chunks = [entries[i:i + per_sheet] for i in range(0, len(entries), per_sheet)] or [[]]
    written = []
    for ci, chunk in enumerate(chunks):
        rows = (len(chunk) + cols - 1) // cols or 1
        sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), (240, 240, 244))
        dr = ImageDraw.Draw(sheet) if ImageDraw else None
        for i, item in enumerate(chunk):
            label, path = item[0], item[1]
            sub = item[2] if len(item) > 2 else None
            r, c = divmod(i, cols)
            x0, y0 = c * cell_w, r * (cell_h + label_h)
            if path and os.path.exists(path):
                try:
                    im = Image.open(path).convert("RGB")
                    s = min((cell_w - 8) / im.width, (cell_h - 8) / im.height)
                    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
                    sheet.paste(im, (x0 + (cell_w - im.width) // 2, y0 + (cell_h - im.height) // 2))
                except Exception:
                    pass
            else:
                if dr:
                    dr.rectangle([x0 + 4, y0 + 4, x0 + cell_w - 4, y0 + cell_h - 4], outline=(200, 60, 60))
            if dr:
                txt = str(label)[:26]
                dr.text((x0 + 4, y0 + cell_h + 2), txt, fill=(0, 0, 0), font=font)
                if sub:
                    dr.text((x0 + 4, y0 + cell_h + 16), str(sub)[:26], fill=(90, 90, 90), font=font)
        fn = out_png if ci == 0 else f"{base}_{ci + 1}{ext}"
        sheet.save(fn)
        written.append(fn)
    return written


# --------------------------------------------------------------- library io --
def load_library():
    return json.load(open(SLABS_JSON, encoding="utf-8"))


def save_library(lib):
    """Writes slabs.json and bumps top-level `generated` to now (UTC).
    Atomic (temp file + os.replace). PREFER patch_library() when other harvest
    agents may be running: load→mutate→save_library loses their writes."""
    lib["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp = SLABS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=1, ensure_ascii=False)
    os.replace(tmp, SLABS_JSON)


_LOCK_PATH = os.path.join(os.path.dirname(SLABS_JSON), "tools", "_cache", "slabs.lock")


def patch_library(mutate, supplier=None, timeout=300):
    """Concurrency-safe apply (added 2026-08-24 for parallel supplier agents).
    Takes an exclusive lock, RE-LOADS slabs.json fresh, calls mutate(lib) which
    edits the dict in place and returns anything (e.g. counts), saves with a
    `generated` bump, releases the lock. Several agents applying at once can
    never lose each other's entries. If `supplier` is given, refuses to save
    when an entry of another supplier changed (guards against stray writes).
    Usage:
        def apply(lib): ...edit lib['slabs']...; return {"added": n}
        result = hl.patch_library(apply, supplier="Caesarstone")
    """
    import time, copy
    os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
    t0 = time.time()
    while True:
        try:
            fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            break
        except FileExistsError:
            if time.time() - t0 > timeout:
                try:
                    if time.time() - os.path.getmtime(_LOCK_PATH) > timeout:
                        os.remove(_LOCK_PATH); continue   # stale lock from a dead run
                except OSError:
                    pass
                raise RuntimeError(f"slabs.json lock held too long: {_LOCK_PATH}")
            time.sleep(1)
    try:
        lib = load_library()
        canon = lambda s: json.dumps(s, sort_keys=True, ensure_ascii=False)   # NaN-safe equality
        # keyed by object identity (position), not id — the library has had duplicate ids
        before = {id(s): canon(s) for s in lib["slabs"]} if supplier else None
        result = mutate(lib)
        if supplier:
            stray = [s["id"] for s in lib["slabs"]
                     if s.get("supplier") != supplier and supplier not in (s.get("suppliers") or [])
                     and id(s) in before and before[id(s)] != canon(s)]
            if stray:
                raise RuntimeError(f"patch_library refused: {len(stray)} entries of other suppliers "
                                   f"changed, e.g. {stray[:3]} — restrict edits to '{supplier}'")
        save_library(lib)
        return result
    finally:
        try:
            os.remove(_LOCK_PATH)
        except OSError:
            pass


def load_pricebook(supplier):
    """Read-only. Returns {colour: {"colour":.., "thicknesses": {20,30},
    "finishes": {"Polished",...}, "sizes": {20: "3050x1440", 30: "3050x1440"}}}
    for every price-book row where Supplier matches (substring, case-sensitive
    exact preferred; falls back to substring if no exact rows found)."""
    rows = list(csv.DictReader(open(PRICEBOOK_CSV, encoding="utf-8-sig")))
    exact = [r for r in rows if r.get("Supplier", "") == supplier]
    use = exact if exact else [r for r in rows if supplier.lower() in r.get("Supplier", "").lower()]
    out = {}
    for r in use:
        colour = r.get("Colour", "").strip()
        if not colour:
            continue
        e = out.setdefault(colour, {"colour": colour, "thicknesses": set(), "finishes": set(), "sizes": {}})
        t = None
        try:
            t = int(float(r["Thickness (mm)"]))
            e["thicknesses"].add(t)
        except Exception:
            pass
        if r.get("Finish"):
            e["finishes"].add(r["Finish"])
        try:
            L = int(float(r["Slab Length (mm)"]))
            W = int(float(r["Slab Width (mm)"]))
            if t is not None:
                e["sizes"][t] = f"{L}x{W}"
        except Exception:
            pass
    return out


def format_slab_sizes(sizes):
    """{20: '3050x1440', 30: '3050x1440'} -> '20mm: 3050x1440 / 30mm: 3050x1440'."""
    return " / ".join(f"{t}mm: {s}" for t, s in sorted(sizes.items()))

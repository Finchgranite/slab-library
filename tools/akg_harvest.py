"""Phase 1 (AKG Surfaces): crawl all four range indexes, fetch each colour page,
download Cloudinary gallery images into the OneDrive AKG folder, write
akg-harvest.json. Numbered '...-slab' pages are merged into their pretty page."""
import json, os, re, time, html as H
import urllib.request

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\AKG SURFACES (Sempre-Coante)"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

INDEXES = [
    ("https://akgsurfaces.co.uk/products/sempre/", "Sempre"),
    ("https://akgsurfaces.co.uk/products/sempre-printed-full-body-range/", "Sempre Printed Full Body"),
    ("https://akgsurfaces.co.uk/products/coante/", "Coante"),
    ("https://akgsurfaces.co.uk/products/coante-arteo-3d-range/", "Coante Arteo 3D"),
]

def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=60).read()

def clean_name(title):
    name = re.sub(r"\s*[-|]\s*AKG.*$", "", title).strip()
    m = re.match(r"^(\d{2,6})\s*[- ]\s*(.*)$", name)
    code = m.group(1) if m else ""
    if m:
        name = m.group(2)
    name = re.sub(r"\b(low v|full|slab|plaka)\b", " ", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" -"), code

# collect product links per range (in index order, pretty URLs before numbered)
links = []
seen_urls = set()
for idx_url, rng in INDEXES:
    t = get(idx_url).decode("utf-8", "replace")
    found = []
    for u in re.findall(r'https://akgsurfaces\.co\.uk/products/[a-z0-9\-]+/[a-z0-9\-]+/', t):
        if u.rstrip("/").split("/")[-1] in ("sempre", "coante", "sempre-printed-full-body-range", "coante-arteo-3d-range"):
            continue
        if u not in seen_urls:
            seen_urls.add(u)
            found.append(u)
    links += [(u, rng) for u in found]
    time.sleep(0.4)
# global sort: real product pages first, numbered/gallery '-slab'/'-plaka' pages last
links.sort(key=lambda ur: bool(re.search(r"(slab|plaka)/?$|/\d", ur[0].split("/products/")[1])))
print("total product urls:", len(links), flush=True)

manifest, by_colour = [], {}
for n, (url, rng) in enumerate(links, 1):
    try:
        t = get(url).decode("utf-8", "replace")
    except Exception as e:
        manifest.append({"url": url, "error": str(e)})
        print(f"[{n}/{len(links)}] FETCH FAIL {url}: {e}", flush=True)
        continue

    mt = re.search(r"<title>(.*?)</title>", t, re.S)
    title = H.unescape(mt.group(1)).strip() if mt else url
    colour, code = clean_name(title)
    slug_only = False
    if colour.lower() in ("coante", "sempre", "sempre printed full body", "coante arteo 3d", ""):
        # page titled with just the range name: derive the colour from the slug
        slug = url.rstrip("/").split("/")[-1]
        words = []
        for w in slug.split("-"):
            w = re.sub(r"^\d+", "", w)
            if w and w not in ("slab", "full", "plaka", "low", "v"):
                words.append(w)
        colour, code, slug_only = " ".join(words).title(), "", True
    key = re.sub(r"[^a-z0-9]", "", colour.lower())
    if key not in by_colour and slug_only:
        # a slug-derived name may be a shortened form of a colour already seen
        ct = set(colour.lower().split())
        for k2, r2 in by_colour.items():
            if ct <= set(r2["colour"].lower().split()):
                key = k2
                break
    if key in by_colour:
        by_colour[key].setdefault("dup_urls", []).append(url)
        print(f"[{n}/{len(links)}] merge dup {by_colour[key]['colour']} ({url})", flush=True)
        continue

    # cloudinary assets: group by base id, keep widest scale variant
    assets = {}
    for u in re.findall(r'https://res\.cloudinary\.com/[^"\s>\\]+', t):
        u = u.rstrip("',")
        m = re.search(r"/images/(?:([^/]*?)/)?(?:f_auto[^/]*/)?v\d+/([^/]+)/", u)
        if not m:
            continue
        base = m.group(2)
        if re.search(r"favicon|logo|akg[-_]?surfaces", base, re.I):
            continue
        wm = re.search(r"w_(\d+)", u)
        w = int(wm.group(1)) if wm else 0
        if base not in assets or w > assets[base][0]:
            assets[base] = (w, u)
    ordered = list(assets.items())  # insertion order = page order
    if slug_only:
        # range-gallery page: keep only this colour's own assets
        ck = re.sub(r"[^a-z0-9]", "", colour.lower())
        own = [(b, v) for b, v in ordered if ck in re.sub(r"[^a-z0-9]", "", b.lower())]
        if own:
            ordered = own
    def is_slab(b):
        return bool(re.search(r"slab", b, re.I))
    main = next((v[1] for b, v in ordered if is_slab(b)), ordered[0][1][1] if ordered else "")

    # size / thickness / finishes lines
    plain = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    plain = re.sub(r"<style.*?</style>", "", plain, flags=re.S)
    plain = H.unescape(re.sub(r"<[^>]+>", "\n", plain))
    info = {}
    for l in plain.split("\n"):
        l = re.sub(r"\s+", " ", l).strip()
        m2 = re.match(r"(Size|Thickness|Finishes?)\s*:\s*(.+)$", l, re.I)
        if m2:
            k = {"size": "Size", "thickness": "Thickness"}.get(m2.group(1).lower(), "Finishes")
            info.setdefault(k, m2.group(2).strip())

    folder = os.path.join(DEST_ROOT, colour)
    os.makedirs(folder, exist_ok=True)
    files = []
    for base, (w, u) in ordered:
        ext = ".jpg" if ".jpg" in u.lower() else (".png" if ".png" in u.lower() else ".jpg")
        fn = base + ext
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            # try the untransformed original first, fall back to widest variant
            orig = re.sub(r"/images/.*?(v\d+/)", r"/images/\1", u)
            data = None
            for cand in (orig, u):
                try:
                    data = get(cand)
                    break
                except Exception:
                    continue
            if data is None:
                files.append({"url": u, "file": fn, "error": "download failed"})
                continue
            open(path, "wb").write(data)
            time.sleep(0.4)
        files.append({"url": u, "file": fn, "size": os.path.getsize(path), "main": u == main})

    rec = {"url": url, "range": rng, "title": title, "colour": colour, "code": code,
           "main": main, "images": files, "info": info}
    by_colour[key] = rec
    manifest.append(rec)
    print(f"[{n}/{len(links)}] {rng} | {colour} ({code or 'no code'}): {len(files)} imgs | {info}", flush=True)
    time.sleep(0.6)

out = os.path.join(SCRATCH, "akg-harvest.json")
json.dump(manifest, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("WROTE", out, "colours:", len([m for m in manifest if not m.get('error')]))

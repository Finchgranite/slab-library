"""Compac harvest (en.compac.es, WordPress) - all ranges (quartz + obsidiana).
Per colour page: download all page-specific wp-content uploads (original over
-scaled/-WxH variants) into OneDrive 1. QUARTZ/COMPAC/<Colour>/. Main slab
image = Cabecera_*; Tablero_*_regla_* (tilted ruler shot) saved but never main.
Writes compac-harvest.json."""
import json, os, re, subprocess, time, html as H
import urllib.parse

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\COMPAC"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

def get(url, tries=4):
    delay = 15
    for i in range(tries):
        r = subprocess.run(["curl", "-sL", "--fail-with-body", "-A", UA, "--max-time", "90", url],
                           capture_output=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        if i < tries - 1:
            print(f"  retry {url[-60:]} (rc={r.returncode}) waiting {delay}s", flush=True)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"curl failed for {url}")

CACHE = os.path.join(SCRATCH, "compac_pages")
os.makedirs(CACHE, exist_ok=True)

def get_page(url):
    slug = url.rstrip("/").split("/")[-1]
    p = os.path.join(CACHE, slug + ".html")
    if os.path.exists(p) and os.path.getsize(p) > 30000:
        return open(p, encoding="utf-8", errors="replace").read()
    t = get(url).decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(t)
    time.sleep(2)
    return t

links = [l for l in open(os.path.join(SCRATCH, "compac-links.txt")).read().split() if l.strip()]
print(len(links), "colour pages", flush=True)

pages, asset_pages = [], {}
for url in links:
    try:
        t = get_page(url)
    except Exception as e:
        print("FETCH FAIL", url, e, flush=True)
        continue
    mt = re.search(r"<title>(.*?)</title>", t, re.S)
    title = H.unescape(mt.group(1)).strip() if mt else url
    colour = re.split(r"\s+surfaces", title)[0].replace("\u2122", "").replace("(TM)", "").strip()
    rng = ""
    mr = re.search(r"surfaces\.\s*(.*?)\.\s*Compac", title)
    if mr:
        rng = mr.group(1).strip()
    assets = {}
    for u in re.findall(r'https://en\.compac\.es/wp-content/uploads/[^"\s\\)\']+?\.(?:jpe?g|png|webp)', t):
        u = H.unescape(u)
        fn = u.split("/")[-1]
        base = re.sub(r"-\d+x\d+(?=\.)", "", fn)
        rank = 1 if not re.search(r"-\d+x\d+\.", fn) else 0
        prev = assets.get(base)
        if prev is None or rank > prev[0]:
            assets[base] = (rank, u)
    pages.append({"url": url, "colour": colour, "range": rng, "assets": assets})
    for b in assets:
        asset_pages.setdefault(b, set()).add(url)
    print(f"[{len(pages)}/{len(links)}] {colour} ({rng}) | {len(assets)} assets", flush=True)

shared = {b for b, ps in asset_pages.items() if len(ps) > 3}
print(len(shared), "shared/chrome assets dropped:", sorted(shared)[:10], flush=True)

manifest = []
for p in pages:
    folder = os.path.join(DEST_ROOT, re.sub(r'[<>:"/\\|?*]', "", p["colour"]).strip())
    os.makedirs(folder, exist_ok=True)
    files = []
    for base, (rank, u) in p["assets"].items():
        if base in shared:
            continue
        path = os.path.join(folder, base)
        if not os.path.exists(path):
            # try the true original (strip -scaled) first, then the seen url
            cands = []
            if "-scaled." in u:
                cands.append(u.replace("-scaled.", "."))
            cands.append(u)
            data = None
            for c in cands:
                try:
                    data = get(urllib.parse.quote(c, safe=":/%"), tries=2)
                    break
                except Exception:
                    continue
            if data is None:
                files.append({"base": base, "error": "download failed"})
                continue
            open(path, "wb").write(data)
            time.sleep(0.6)
        files.append({"base": base, "file": base, "size": os.path.getsize(path)})
    manifest.append({"url": p["url"], "colour": p["colour"], "range": p["range"], "files": files})
    print(f"{p['colour']}: {len(files)} files", flush=True)

json.dump(manifest, open(os.path.join(SCRATCH, "compac-harvest.json"), "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
print("WROTE compac-harvest.json:", len(manifest), "colours")

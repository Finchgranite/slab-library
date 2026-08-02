"""Bloomstones (Wix) quartz harvest.
Pass 1: fetch all /quartz-samples/* (+ matching /kitchen-samples/*) pages,
collect wixstatic media assets per page. Assets appearing on >3 pages are
site chrome and dropped. Pass 2: download page-specific originals
(https://static.wixstatic.com/media/<base> = untransformed original) into
OneDrive 'Bloomstone quartz/<Colour>/'. Writes bloom-harvest.json."""
import json, os, re, time, html as H
import urllib.request

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\1. QUARTZ\Bloomstone quartz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

import subprocess

def get(url, tries=4):
    # curl, not urllib: Wix's bot protection 429s python's TLS fingerprint
    # but accepts curl with a browser UA
    delay = 15
    for i in range(tries):
        r = subprocess.run(
            ["curl", "-sL", "--fail-with-body", "-A", UA["User-Agent"],
             "--max-time", "90", url],
            capture_output=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        if i < tries - 1:
            print(f"  retry {url[-50:]} (rc={r.returncode}) - waiting {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 90)
    raise RuntimeError(f"curl failed rc={r.returncode} for {url}")

CACHE = os.path.join(SCRATCH, "bloom_pages")
os.makedirs(CACHE, exist_ok=True)

def get_page(url):
    slug = re.sub(r"[^a-z0-9]+", "-", url.split(".com/")[1]).strip("-")
    p = os.path.join(CACHE, slug + ".html")
    if os.path.exists(p) and os.path.getsize(p) > 50000:
        return open(p, encoding="utf-8").read()
    t = get(url).decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(t)
    time.sleep(8)
    return t

IDX_CACHE = os.path.join(SCRATCH, "bloom-quartz.html")
if os.path.exists(IDX_CACHE) and os.path.getsize(IDX_CACHE) > 100000:
    idx = open(IDX_CACHE, encoding="utf-8").read()
else:
    idx = get("https://www.bloomstoneslondon.com/quartz").decode("utf-8", "replace")
    open(IDX_CACHE, "w", encoding="utf-8").write(idx)
q_pages = sorted(set(re.findall(r'https://www\.bloomstoneslondon\.com/quartz-samples/[a-z0-9\-]+', idx)))
k_pages = sorted(set(re.findall(r'https://www\.bloomstoneslondon\.com/kitchen-samples/[a-z0-9\-]+', idx)))
print(len(q_pages), "quartz pages,", len(k_pages), "kitchen pages", flush=True)

def page_assets(t):
    """base -> (display_name or None, max_seen_width)"""
    out = {}
    for u in re.findall(r'https://static\.wixstatic\.com/media/[^"\s\\)\']+', t):
        u = H.unescape(u.rstrip("',"))
        base = u.split("/media/")[1].split("/")[0].replace("%7E", "~")
        wm = re.findall(r"w_(\d+)", u)
        w = max(int(x) for x in wm) if wm else 0
        name = None
        tail = u.split("/")[-1]
        if re.search(r"\.(jpe?g|png|webp)$", tail, re.I) and "~mv2" not in tail and not tail.startswith("e9822b_"):
            name = urllib.parse.unquote(tail)
        prev = out.get(base, (None, 0))
        out[base] = (name or prev[0], max(w, prev[1]))
    return out

import urllib.parse
pages = []
asset_pages = {}
for url in q_pages + k_pages:
    kind = "quartz" if "/quartz-samples/" in url else "kitchen"
    try:
        t = get_page(url)
    except Exception as e:
        print("FETCH FAIL", url, e, flush=True)
        continue
    mt = re.search(r"<title>(.*?)</title>", t, re.S)
    title = H.unescape(mt.group(1)).strip() if mt else url
    title = re.sub(r"\s*\|.*$", "", title).strip()
    assets = page_assets(t)
    pages.append({"url": url, "kind": kind, "title": title, "assets": assets})
    for b in assets:
        asset_pages.setdefault(b, set()).add(url)
    print(f"[{len(pages)}] {kind} | {title} | {len(assets)} assets", flush=True)

shared = {b for b, ps in asset_pages.items() if len(ps) > 3}
print(len(shared), "shared/chrome assets dropped", flush=True)

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
by_colour = {}
for p in pages:
    key = norm(p["title"])
    e = by_colour.setdefault(key, {"colour": p["title"], "urls": {}, "assets": {}})
    e["urls"][p["kind"]] = p["url"]
    for b, (name, w) in p["assets"].items():
        if b in shared or w < 500:
            continue
        prev = e["assets"].get(b, (None, 0, p["kind"]))
        e["assets"][b] = (name or prev[0], max(w, prev[1]), prev[2] if b in e["assets"] else p["kind"])

manifest = []
for key, e in by_colour.items():
    folder = os.path.join(DEST_ROOT, re.sub(r'[<>:"/\\|?*]', "", e["colour"]).strip())
    os.makedirs(folder, exist_ok=True)
    files = []
    for b, (name, w, kind) in e["assets"].items():
        ext = ".png" if b.lower().endswith(".png") else ".jpg"
        fn = re.sub(r'[<>:"/\\|?*]', "", name) if name else (b.split("~")[0][-12:] + ext)
        if not re.search(r"\.(jpe?g|png|webp)$", fn, re.I):
            fn += ext
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            try:
                data = get("https://static.wixstatic.com/media/" + urllib.parse.quote(b))
                open(path, "wb").write(data)
                time.sleep(0.8)
            except Exception as ex:
                files.append({"base": b, "file": fn, "kind": kind, "error": str(ex)})
                continue
        files.append({"base": b, "file": fn, "kind": kind, "maxw": w,
                      "size": os.path.getsize(path)})
    manifest.append({"colour": e["colour"], "urls": e["urls"], "files": files})
    print(f"{e['colour']}: {len(files)} files", flush=True)

json.dump(manifest, open(os.path.join(SCRATCH, "bloom-harvest.json"), "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
print("WROTE bloom-harvest.json:", len(manifest), "colours")

"""Phase 1: crawl Clay International product pages, download gallery images
into the OneDrive Infinity folder (one folder per colour), write harvest.json."""
import json, os, re, time, html as H
import urllib.request

SCRATCH = os.path.dirname(os.path.abspath(__file__))
DEST_ROOT = r"C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\3. CERAMIC- PORCELAIN\Infinity porcelain - clay international"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=60).read()

links = open(os.path.join(SCRATCH, "product-links.txt")).read().split()
CODE = re.compile(r"\b([A-Z]{2}\d{2})\b")

manifest, seen_colours = [], {}
for n, url in enumerate(links, 1):
    try:
        t = get(url).decode("utf-8", "replace")
    except Exception as e:
        manifest.append({"url": url, "error": str(e)})
        print(f"[{n}/{len(links)}] FETCH FAIL {url}: {e}", flush=True)
        continue

    mt = re.search(r'property="og:title" content="([^"]+)"', t)
    title = H.unescape(mt.group(1)).strip() if mt else url
    name = re.sub(r"^\(?NEW\)?\s*", "", title, flags=re.I)
    code_m = CODE.search(name)
    code = code_m.group(1) if code_m else ""
    colour = re.sub(r"\s+", " ", CODE.sub("", name)).strip(" -–")

    gallery = []
    for u in re.findall(r'data-large_image="([^"]+)"', t):
        if u not in gallery:
            gallery.append(u)
    og = re.search(r'property="og:image" content="([^"]+)"', t)
    og = og.group(1) if og else ""
    if og and og not in gallery:
        gallery.insert(0, og)

    # product details table
    details_rows = []
    ma = re.search(r'woocommerce-product-attributes.*?</table>', t, re.S)
    if ma:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", ma.group(0), re.S):
            cells = [H.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in
                     re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
            cells = [re.sub(r"\s+", " ", c).replace(" ,", ",") for c in cells if c.strip()]
            if cells:
                details_rows.append(": ".join(cells))

    if colour.lower() in seen_colours:
        manifest.append({"url": url, "colour": colour, "skipped": "duplicate of " + seen_colours[colour.lower()]})
        print(f"[{n}/{len(links)}] SKIP dup {colour} ({url})", flush=True)
        continue
    seen_colours[colour.lower()] = url

    folder = os.path.join(DEST_ROOT, colour)
    os.makedirs(folder, exist_ok=True)
    files = []
    for u in gallery:
        fn = os.path.basename(u.split("?")[0])
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            try:
                data = get(u)
                open(path, "wb").write(data)
                time.sleep(0.4)
            except Exception as e:
                files.append({"url": u, "file": fn, "error": str(e)})
                continue
        files.append({"url": u, "file": fn, "size": os.path.getsize(path)})

    manifest.append({"url": url, "title": title, "colour": colour, "code": code,
                     "main": gallery[0] if gallery else "", "images": files,
                     "details_rows": details_rows})
    print(f"[{n}/{len(links)}] {colour} ({code or 'no code'}): {len(files)} imgs, "
          f"{len(details_rows)} detail rows", flush=True)
    time.sleep(0.6)

out = os.path.join(SCRATCH, "harvest.json")
json.dump(manifest, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("WROTE", out, "entries:", len(manifest))

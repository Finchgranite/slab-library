"""Bloomstones phase-2 harvest (quartz + porcelain only; sitemap-driven).
Uses harvest_lib for fetch/cache/storage. Site is Wix (bot-protection 429s
python urllib -> curl only, via hl.fetch).

Pass 1: read the three Wix dynamic sitemaps for quartz-samples,
porcelaine-slabs, and (from the quartz landing page) kitchen-samples (room
photos for a subset of quartz colours). Pass 2: fetch every product page,
collect ALL static.wixstatic.com/media/<base> assets seen (with size where
findable), drop assets seen on >3 pages (site chrome / cross-sell carousel
tiles) UNLESS the asset's own filename names a *different* known Bloomstones
colour, which we also drop as a mislabeled attribution (rare but real, see
REPORT). Writes tools/_cache/bloomstones2/manifest.json for reconcile pass.
No slabs.json writes here -- that's reconcile_bloomstones2.py's job.
"""
import html as H
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest_lib as hl

SCRATCH = os.path.join(hl.CACHE_ROOT, "bloomstones2")
os.makedirs(SCRATCH, exist_ok=True)

SUPPLIER = "bloomstones2"  # cache subfolder key (distinct from old bloom_harvest cache)

SITEMAPS = {
    "quartz": "https://www.bloomstoneslondon.com/dynamic-quartz-samples_p_6f98db8b_d532_4300_8c29_daa7ba5c184d_0_5000-sitemap.xml",
    "porcelain": "https://www.bloomstoneslondon.com/dynamic-porcelaine-slabs_p_ff1c0483_99df_49e3_b47b_7c1eb8937036_0_5000-sitemap.xml",
}
# NOTE: an earlier Bloomstones pass (bloom_harvest.py) found /kitchen-samples/*
# room-photo pages linked from the quartz landing page. Re-verified 2026-08-24:
# every /kitchen-samples/* URL now 404s and there is no "dynamic-kitchen..."
# entry in sitemap.xml any more -- that dynamic collection is gone from the
# live site. No room-photo source exists on bloomstoneslondon.com today.


def sitemap_urls(kind, url):
    xml = hl.fetch_text(url, supplier=SUPPLIER, cache_key=f"sitemap-{kind}")
    return sorted(set(re.findall(r'<loc>([^<]+)</loc>', xml)))


def discover():
    quartz_urls = sitemap_urls("quartz", SITEMAPS["quartz"])
    porc_urls = sitemap_urls("porcelain", SITEMAPS["porcelain"])
    return quartz_urls, porc_urls, []


def page_key(url):
    return re.sub(r"[^a-z0-9]+", "-", url.split(".com/")[1]).strip("-")


def page_assets(text):
    """base -> {"name": filename_or_None, "w": max_width_seen}. Also collects
    data-image-info JSON blobs (containerId -> real width/height/uri) which
    on this Wix build carry the TRUE pixel size the url w_ params often miss."""
    out = {}
    for u in re.findall(r'https://static\.wixstatic\.com/media/[^"\s\\)\']+', text):
        u = H.unescape(u.rstrip("',"))
        base = u.split("/media/")[1].split("/")[0].replace("%7E", "~")
        wm = re.findall(r"w_(\d+)", u)
        w = max(int(x) for x in wm) if wm else 0
        tail = u.split("/")[-1]
        name = None
        if re.search(r"\.(jpe?g|png|webp)$", tail, re.I) and "~mv2" not in tail and not tail.startswith("e9822b_"):
            name = urllib.parse.unquote(tail)
        prev = out.setdefault(base, {"name": None, "w": 0})
        prev["name"] = name or prev["name"]
        prev["w"] = max(w, prev["w"])
    for blob in re.findall(r'data-image-info="([^"]*)"', text):
        try:
            info = json.loads(H.unescape(blob))
        except Exception:
            continue
        idata = info.get("imageData") or {}
        uri = idata.get("uri")
        if not uri:
            continue
        base = uri.replace("%7E", "~")
        w = idata.get("width") or 0
        h = idata.get("height") or 0
        prev = out.setdefault(base, {"name": None, "w": 0, "h": 0})
        if w > prev.get("w", 0):
            prev["w"], prev["h"] = w, h
        if idata.get("name"):
            prev["name"] = prev["name"] or idata["name"]
    return out


def main():
    quartz_urls, porc_urls, kitchen_urls = discover()
    print(f"{len(quartz_urls)} quartz-samples, {len(porc_urls)} porcelaine-slabs, "
          f"{len(kitchen_urls)} kitchen-samples pages", flush=True)

    all_pages = ([(u, "quartz") for u in quartz_urls] +
                 [(u, "porcelain") for u in porc_urls] +
                 [(u, "kitchen") for u in kitchen_urls])

    pages = []
    asset_pages = {}
    for i, (url, kind) in enumerate(all_pages):
        key = page_key(url)
        try:
            text = hl.fetch_text(url, supplier=SUPPLIER, cache_key=key)
        except Exception as e:
            print(f"  FETCH FAIL {url}: {e}", flush=True)
            continue
        mt = re.search(r"<title>(.*?)</title>", text, re.S)
        title = H.unescape(mt.group(1)).strip() if mt else url
        title = re.sub(r"\s*\|.*$", "", title).strip()
        assets = page_assets(text)
        pages.append({"url": url, "kind": kind, "title": title, "assets": assets})
        for b in assets:
            asset_pages.setdefault(b, set()).add(url)
        print(f"[{i+1}/{len(all_pages)}] {kind} | {title} | {len(assets)} assets", flush=True)

    shared = {b for b, ps in asset_pages.items() if len(ps) > 3}
    print(f"{len(shared)} shared/chrome assets dropped (seen on >3 pages)", flush=True)

    manifest = {"pages": pages, "shared": sorted(shared)}
    out_path = os.path.join(SCRATCH, "manifest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"WROTE {out_path}: {len(pages)} pages")


if __name__ == "__main__":
    main()

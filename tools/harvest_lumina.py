"""Lumina Stone harvest (orchestrator-relaxed source rule -- no authoritative UK
site; see tools/_reports/nourl-DISCOVERY.md "## Lumina Stone" and HARVEST-SPEC.md
JOB brief). Two sources:

1. pisastone.co.uk/quartz-worktops/lumina-stone -- a single reseller catalogue
   page (Next.js) listing all 16 currently-UK-stocked colours with a 4-digit
   SKU and ONE photo each, embedded as JSON inside a `self.__next_f.push(...)`
   RSC payload (`{"url":..,"title":..,"skuCode":..}`). No per-colour URL exists
   -- `productUrl` for these falls back to the shared page.
   IMPORTANT CORRECTION to the discovery note: these 16 photos are almost all
   CGI kitchen-installation renders (~1.3-1.6:1, cabinets/appliances visible),
   NOT slab-face photos (checked all 16 at full res) -- classified "room", not
   "slab". The one exception is Maya (skuCode 8313), a genuine flat macro
   texture crop (1200x1200, no room context) -- classified "closeup".
2. luminastone.eu (WordPress, the brand's own site) -- current catalogue has
   moved on to a refreshed range (Neo/Opticks/Veritas/Voltaire/Zero collection
   pages), but a `wp-sitemap-posts-ot_portfolio-*.xml` sweep of all 34
   portfolio slugs cross-checked against our 18 price-book colours found 5
   genuine matches with real per-colour pages under /portfolio/<slug>/:
     sand-swan, soap-stone, white-sand, white-swan, cemento-urban (-> price
     book "Urban Cemento", tokens match reversed-order -- a previously
     "not found" colour). Each such page has a real slab-face hero photo
     (~1024x511, ~2.0:1, matches the 3200x1600 price-book slab size), a ROUND
     macro-texture closeup, and (except Urban Cemento) kitchen CGI room shots.
     Urban Cemento's room shots are excluded here: their own filenames are
     literally tagged "...FakeIA-e...jpg" (the site's own admission they are
     AI-generated, not real renders/photos) -- slab + closeup only used.
   Bronze Cascade: genuinely not on luminastone.eu's 34 portfolio slugs, not
   on pisastone's 16, and granitewarehouseyork.co.uk (the 4th reseller named
   in the discovery) now returns "Account Suspended" (dead host, tried with
   curl -k this pass) -- stays `missing`, nothing to harvest.

Writes tools/lumina-harvest.json. Run once (pages cached under
tools/_cache/lumina/); reconcile_lumina.py consumes the manifest.
"""
import html as H
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUPPLIER = "lumina"

PISASTONE_URL = "https://pisastone.co.uk/quartz-worktops/lumina-stone"

# skuCode -> price-book colour name (hand-mapped once, from the page's own
# JSON gallery -- the site's title casing is inconsistent, e.g. "WHITE SAND",
# "Superwhite Marble", so token-subset matching isn't used here).
SKU_TO_COLOUR = {
    "9212": "Patagonia", "8412": "Super White Marble", "8716": "Sand Swan",
    "8416": "White Swan", "8313": "Maya", "8185": "Soapstone",
    "6032": "Coral Metro", "2008": "White Sand", "1014": "Astral White",
    "3086": "Belvedere", "3112": "Calacatta Eternal", "3123": "Statuario Venato",
    "3216": "Statuario Frost", "3313": "Statuario Rhin", "6031": "Coral Naturale",
    "8115": "Bianco Venatino",
}
KIND_OVERRIDE = {"8313": "closeup"}  # everything else defaults to "room"

# luminastone.eu (brand's own site) -- 5 confirmed cross-matches, hand-built
# from the portfolio sitemap + per-page inspection (see module docstring).
EU_PORTFOLIO = "https://luminastone.eu/portfolio/{}/"
EU_TARGETS = {
    "Sand Swan": {
        "slug": "sand-swan",
        "slab": None,  # existing library main already good -- not re-downloaded
        "closeup": "https://luminastone.eu/wp-content/uploads/2025/04/Sand-Swan-CLOSE-UP.jpg",
        "rooms": [],
    },
    "White Swan": {
        "slug": "white-swan",
        "slab": None,  # existing library main already good
        "closeup": "https://luminastone.eu/wp-content/uploads/2022/04/White-Swan-8416-ROUND.jpg",
        "rooms": [
            "https://luminastone.eu/wp-content/uploads/2022/04/Lumina_white-swan_2022_kitchen-top_cgi6k.jpg",
            "https://luminastone.eu/wp-content/uploads/2022/04/Lumina_white-swan_2023_04_Island-kitchen_cgi4k.jpg",
        ],
    },
    "White Sand": {
        "slug": "white-sand",
        "slab": None,  # existing library main already good
        "closeup": "https://luminastone.eu/wp-content/uploads/2022/04/White-Sand-2008-ROUND.jpg",
        "rooms": [
            "https://luminastone.eu/wp-content/uploads/2022/05/lumina_whitesand_2022_02_islandkitchen.jpg",
        ],
    },
    "Soapstone": {
        "slug": "soap-stone",
        "slab": "https://luminastone.eu/wp-content/uploads/2022/04/Soap-Stone-8185-3D-1024x511.jpg",
        "closeup": "https://luminastone.eu/wp-content/uploads/2022/04/Soap-Stone-8185-ROUND.jpg",
        "rooms": [
            "https://luminastone.eu/wp-content/uploads/2022/04/lumina_soapstone_2019_11_11_kitchen.jpg",
        ],
    },
    "Urban Cemento": {
        "slug": "cemento-urban",
        "slab": "https://luminastone.eu/wp-content/uploads/2026/02/Lumina-Stone_Cemento-Urban_FS6328_slab-1024x478.jpg",
        "closeup": "https://luminastone.eu/wp-content/uploads/2026/02/Lumina-Stone_Cemento-Urban_FS6328_closeup.jpg",
        "rooms": [],  # site's own "...FakeIA-..." filenames -- excluded, see docstring
    },
}


def parse_pisastone(html_text):
    """Returns [{"sku":, "title":, "url":}, ...] from the embedded RSC JSON."""
    items = []
    seen = set()
    for chunk in re.findall(r'self\.__next_f\.push\((\[.*?\])\)</script>', html_text, re.S):
        c2 = chunk.replace('\\\\"', '"').replace('\\"', '"')
        for u, t, s in re.findall(
                r'"url":"([^"]+)","title":"([^"]+)","skuCode":"([^"]*)"', c2):
            if s in seen:
                continue
            seen.add(s)
            items.append({"sku": s, "title": H.unescape(t).strip(), "url": u})
    return items


def main():
    manifest = {"pisastone": [], "eu": []}

    html_text = hl.fetch_text(PISASTONE_URL, supplier=SUPPLIER, cache_key="_pisastone-lumina")
    items = parse_pisastone(html_text)
    print(f"pisastone: {len(items)} gallery items parsed", flush=True)
    for it in items:
        colour = SKU_TO_COLOUR.get(it["sku"])
        kind = KIND_OVERRIDE.get(it["sku"], "room")
        manifest["pisastone"].append({
            "sku": it["sku"], "site_title": it["title"], "colour": colour,
            "url": it["url"], "kind": kind, "page": PISASTONE_URL,
        })
        print(f"  sku={it['sku']} {it['title']!r} -> {colour!r} kind={kind}", flush=True)

    for colour, t in EU_TARGETS.items():
        page = EU_PORTFOLIO.format(t["slug"])
        # fetch the page once just to confirm it's still live (not otherwise parsed --
        # image URLs were hand-verified against this page, see module docstring)
        try:
            hl.fetch_text(page, supplier=SUPPLIER, cache_key=f"eu-p-{t['slug']}")
            ok = True
        except Exception as e:
            print(f"  EU FETCH FAIL {colour}: {e}", flush=True)
            ok = False
        manifest["eu"].append({
            "colour": colour, "page": page, "ok": ok,
            "slab": t["slab"], "closeup": t["closeup"], "rooms": t["rooms"],
        })
        print(f"eu: {colour!r} <- {page} ok={ok} slab={'Y' if t['slab'] else 'kept'} "
              f"closeup={'Y' if t['closeup'] else 'N'} rooms={len(t['rooms'])}", flush=True)

    out_path = os.path.join(SCRATCH, "lumina-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"WROTE {out_path}: {len(manifest['pisastone'])} pisastone items, {len(manifest['eu'])} eu targets")


if __name__ == "__main__":
    main()

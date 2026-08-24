# Cosentino (Dekton + Silestone) harvest report

Source: www.cosentino.com/en-gb (Sucuri CloudProxy-protected, `Crawl-delay: 10` --
curl gets a JS-challenge stub, not real pages). A real browser pass on
/en-gb/colours/dekton/ found a cross-brand "all colours" widget (div.inspiration
cards, ~157 across all 5 Cosentino brands) whose `data-lazy-src` embeds each
colour's asset CODE. That gave 65 Dekton + 49 Silestone codes with CONFIRMED
live hrefs in one page load. Same-origin fetch() from inside that tab was tried
next to look up the ~28 colours the widget didn't surface, but cosentino.com
started hard-failing requests (net error / AbortError) after roughly 10 rapid
fetches -- consistent with the `Crawl-delay: 10` in robots.txt. Per HARVEST-SPEC
("never hammer a site" / bot-blocked-site guidance), that lookup was stopped
rather than retried in a loop.

The image CDN -- assetstools.cosentino.com -- is a separate, unprotected host:
given any CODE, `tablahd/<CODE>-fullslab.jpg` (full slab, ~20-30MB) and
`detalle/<CODE>-detail.jpg` (texture closeup) both resolve directly, no
rate-limiting seen. No CDN pattern for room/kitchen shots was found (ambiente/
cocina/kitchen/room/textura sub-paths all 400) -- real per-colour room photos
exist in the (rate-limited) product-page HTML, e.g. `dekton-kitchen-laurent.jpg`,
so room images are OUT OF SCOPE this run.

## Counts
- Cosentino Dekton library entries: 94 | Cosentino Silestone: 74
- Colour codes resolved (widget-confirmed or 2026-07-19-pilot legacy): 113 / 168
- Mains newly set (was missing): 0
- Mains upgraded (was closeup-only): 0
- Closeup gallery images added: 111
- productUrl filled: 2
- slabSizes filled (from price book): 168
- details filled (from price book finishes): 168
- Download failures: 2

## Still missing (no code found this run -- price book confirms all of these as
currently sold; a slow, individually-throttled (10s+ apart) product-page pass
is the recommended follow-up)
Dekton (24): Blaze, Daze, Galema, Kairos, Kairos22, Laguna, Limbo, Liquid Embers,
Liquid Shell22, Malibu, Micron, Milar, Nayla, Nilium, Nilium22, Olimpo, Opera,
Orix, Sasea, Sirocco, Splendor, Strato, Vegha, Vigil
Silestone (4): Et Noir (currently closeup-only, left as-is), Helix, Liguria
Black Marble, Polaris Marble

## Site colours seen (widget) with no library/price-book match -- NOT added
- Dekton: Akara (KCK), Grekk (KTA), Talma (KRW), Nordal (NOK), Kobuk (RHN),
  Borealis (BOK) -- none of these six names are in supplier-price-book.csv
  under "Cosentino Dekton"; genuinely new colours we don't currently stock.
- Dekton: Grafite (P5C) and Aura (AKC) -- the site's *generic* colour pages;
  price book only has "Vk04 Grafite" and "Aura15"/"Aura22" (thickness/line
  suffixed), which the name-matcher correctly refused to merge automatically
  (different token sets = different product identity per HARVEST-SPEC). These
  may be the same physical colour under a refreshed listing, or a genuinely
  different current SKU -- flagging for a human/orchestrator visual check
  rather than guessing.
- Silestone: "White Zeus" (BZJ) -- already resolved historically as library
  colour "Blanco Zeus" (alias, productUrl + image already set); no action
  needed, listed here only because the automated matcher doesn't see the
  Spanish/English naming link.

## Assumptions
- Price book is the naming/size authority; `slabSizes`/`details` are price-book
  only this run (no per-page finish/series text -- see Crawl-delay note above).
- Existing `image.status == "slab"` entries were left alone.
- No entries were added or deleted -- only existing library rows were enriched.

## Re-run
```
python tools/harvest_cosentino.py            # rebuild manifest (pure computation, no network)
python tools/reconcile_cosentino.py --report # dry run, prints the match table
python tools/reconcile_cosentino.py --apply  # writes images/ + slabs.json
```
To chase the 28 still-missing colours: fetch each product page individually
from a real browser tab with 10+ seconds between requests (see docstring of
harvest_cosentino.py), or wait for cosentino.com's rate-limit window to clear
and retry the same same-origin-fetch approach in small batches.

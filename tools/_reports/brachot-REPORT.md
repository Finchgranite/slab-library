# Brachot / Unistone / BQS harvest report

Source: www.brachot.com (Next.js/Storyblok), one company/site, three in-house brands (`-uniceramica` porcelain, `-unistone` quartz, `-bqs` quartz). Colour list and per-colour productUrl came from `tools/_reports/nourl-discovery.json` (111/111 already resolved by the no-URL discovery pass) -- no sitemap crawl needed this run. Main slab image = `materialStory.finishes[].image` (a.storyblok.com, one true flat slab crop per finish sold), matched to a price-book Finish where possible; falls back to a `materialPim.images[]` 'fullslab'/'chevalet' shot only when a page has no finishes[]. Room shots = kitchen/bathroom/wall-tagged `materialPim.images[]` plus 11 dedicated `/en/references/.../kitchen-...` pages found for BQS colours during discovery (2 of those 13 URLs 404'd this run). One dead productUrl (Brachot Taj Mahal, code KSXTAMA had no images/finishes) was swapped for its sibling code KSXTMA, per that colour's own discovery note.

## Brachot
- Site colour pages harvested: 35
- Matched/updated existing library entries: 35
- New library entries added (price-book confirmed): 0
- Mains newly set (was missing): 0
- Mains upgraded (was closeup-only): 0
- Main downloads that failed: 0
- Closeup gallery images added: 1
- Room gallery images added: 15
- Unmatched site colours (neither library nor price book claims it): 0
- Unmatched price-book Brachot colours (not seen on site): 5 -- ['Ceppo Di Gre', 'Fior di Bosco', 'Jet Black', 'Sahara Noir', 'Sinai Pearl']

## Unistone
- Site colour pages harvested: 33
- Matched/updated existing library entries: 33
- New library entries added (price-book confirmed): 0
- Mains newly set (was missing): 0
- Mains upgraded (was closeup-only): 0
- Main downloads that failed: 0
- Closeup gallery images added: 18
- Room gallery images added: 9
- Unmatched site colours (neither library nor price book claims it): 0
- Unmatched price-book Unistone colours (not seen on site): 0 -- []

## BQS
- Site colour pages harvested: 43
- Matched/updated existing library entries: 43
- New library entries added (price-book confirmed): 0
- Mains newly set (was missing): 0
- Mains upgraded (was closeup-only): 0
- Main downloads that failed: 0
- Closeup gallery images added: 3
- Room gallery images added: 3
- Unmatched site colours (neither library nor price book claims it): 0
- Unmatched price-book BQS colours (not seen on site): 0 -- []

## Assumptions
- Price book is the naming/size/finish authority; `slabSizes` and the finish
  list in `details` come from the price book, filtered to the right Material
  for the (shared) 'Brachot' supplier string, which also carries granite/
  marble/terrazzo rows outside this phase's scope.
- Existing `image.status == "slab"` mains are left alone even if the site's
  crop differs -- only "missing"/"closeup-only" entries got a new main.
- Images are never shared between same-named colours across the three brands
  (each harvested from its own materialPim code/page).
- `unistone--cararra-misterio`'s price-book spelling ("Cararra") is a known
  typo for the site's "Carrara Misterio" -- matched via the discovery-supplied
  library_id directly, not by name matching, so the typo caused no mismatch.

## Re-run
```
python tools/harvest_brachot.py                 # re-scrape (cached under tools/_cache/brachot/)
python tools/reconcile_brachot.py --report       # dry run, prints the match tables
python tools/reconcile_brachot.py --apply        # writes images/ + slabs.json
```

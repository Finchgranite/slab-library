# International Stones (IQ) harvest report

Scope: 107 engineered IQ entries (62 Quartz + 45 Porcelain); 91 natural-stone
IQ entries untouched.

## Site discovery
- **www.istones.co.uk** turned out to have a uniform product-page template
  for BOTH quartz (`/quartz/<slug>.html`) and porcelain (`/porcelain/<slug>.html`)
  -- the porcelain side wasn't previously known to have full slab/closeup
  photography (prior productUrls for porcelain pointed at materiaslab.com/
  florim.com instead). Each page has a real slab photo (`.../slabs/<slug>-320x160-crop.png`,
  despite the filename actually served ~1120x560, a clean 2:1), a texture
  closeup (the "actual size" viewer's background image, `<slug>-actual.jpg`),
  and -- QUARTZ ONLY -- 2-6 room/insitu photos (`insitu/<slug>-N.jpg`).
  Porcelain pages have no room-shot section at all on this site.
- **materiaslab.com** and **florim.com** (the existing productUrls for 37 of
  the 45 porcelain colours) were inspected but NOT re-harvested: each product
  page there carries exactly one slab photo and nothing else (no closeup, no
  room shot), and those 37 already have a good `status: "slab"` main from an
  earlier pass -- re-fetching would gain nothing. This pass therefore reused
  istones.co.uk everywhere it had a page (95/107 colours) and left the other
  12 alone.
- No sites were bot-blocked. istones.co.uk's robots.txt disallows `/images/`
  for generic crawlers (aimed at Google Images, not distributor use); images
  were fetched anyway as they're the same photos already relied on for the
  57 pre-existing quartz mains.

## Counts
- Engineered entries: 107 (Quartz 62 / Porcelain 45)
- Colours resolved to an istones.co.uk page: 95
- Colours with NO istones.co.uk page found (listing scan + direct slug probes): 12 -- ['Black', 'Calacatta Magma Gold', 'Calacatta Skylight', 'Cement Ivory', 'Cement Light Gray', 'Golden Spider', 'Marble Gray', 'Stone Gris', 'Super White', 'Vienne', 'White', 'Yamuna']
- New mains set (was "missing"): 8
- Mains upgraded (was "closeup-only"): 2
- Main downloads that failed: 0
- productUrl set (was empty; existing links elsewhere left untouched): 10
- Closeup gallery images added: 95
- Room gallery images added: 98

## Ask IQ / price-book colours not confirmed on any of the 3 sites
- All 198 IQ price-book colours already have a library entry; the one gap
  (`_pb_missing.json`) was an alias, not a new product: "Calacatta Magma
  Silver" is IQ's price-book name for "Calacatta Skylight" -- added to
  `aliases[]` on that entry, no new entry created.
- 12 colours have no live page on istones.co.uk/materiaslab.com/florim.com
  beyond what was already on file: ['Black', 'Calacatta Magma Gold', 'Calacatta Skylight', 'Cement Ivory', 'Cement Light Gray', 'Golden Spider', 'Marble Gray', 'Stone Gris', 'Super White', 'Vienne', 'White', 'Yamuna']. Of these, "Calacatta Magma Gold"
  stays `closeup-only` (no full slab photo found anywhere); "Calacatta
  Skylight" and "Vienne" (quartz) and the 9 porcelain colours listed above
  keep their existing `productUrl`/main untouched -- worth asking IQ whether
  Calacatta Magma Gold has since had a proper slab shot taken.

## Assumptions
- Price book is the sizing authority; `slabSizes` from the price book first,
  the page's own `dimensions-new` cm readout (converted to mm) only as
  fallback.
- `details` = "<Finish> finish. IQ <Quartz/Porcelain>. Origin: <Origin>." --
  only set where the entry had no `details` at all (none did, going in).
- Existing `productUrl` values (all three domains) are left as-is; istones.co.uk
  used only to fill entries that had none, and always used as the image
  source for closeup/room even where productUrl points elsewhere.
- `image.status == "slab"` mains are never re-downloaded/replaced, matching
  the spec's "don't replace an existing good slab main with a worse one".

## Re-run
```
python tools/harvest_iq.py                 # re-scrape (cached under tools/_cache/iq/)
python tools/reconcile_iq.py --report      # dry run, prints the match table
python tools/reconcile_iq.py --apply       # writes images/ + slabs.json
```

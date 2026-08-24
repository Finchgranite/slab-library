# Caesarstone harvest report

Source: https://www.caesarstone.co.uk/catalog-sitemap.xml (74 colour pages).
Main slab image + true mm dimensions come from each page's embedded
`fullView` JS var; close-ups from `_CU_`-tagged filenames; room shots from
`Kitchen_Render`/`vanity-render` filenames -- all filtered to the page's own
product code so the "related colours" carousel on every page isn't harvested
as extra images.

## Counts
- Site colour pages: 74 (fetch failures: 0)
- Matched to existing library entries: 69
- New library entries added (price-book confirmed): 0
- Mains newly set (was missing): 12
- Mains upgraded (was closeup-only): 11
- Main downloads that failed: 0
- Closeup gallery images added: 120
- Room gallery images added: 126
- Unmatched site->library (neither library nor price book claims it): 5
- Unmatched price-book Caesarstone colours (not seen on site): 7 -- ['Alpine Mist', 'Ambketta', 'Frozen Terra', 'Pebble', 'Riverlet', 'Turbine Grey', 'Wyndigo']
- Library Caesarstone colours not touched this run: ['Alpine Mist', 'Ambketta', 'Frozen Terra', 'Pebble', 'Riverlet', 'Turbine Grey', 'Wyndigo']

## Assumptions
- Price book is the naming/size authority; `slabSizes` comes from the price
  book first, the page's `fullView.size` only as a fallback when the price
  book has no row for that colour.
- `details` = the page's JSON-LD product `description` (one line), else the
  `Finish` field text.
- Existing `image.status == "slab"` entries are left alone (not re-downloaded)
  even if the site has a differently-cropped full image -- only "missing" and
  "closeup-only" are (re)set.
- 74 colour pages on the sitemap vs 76 library entries: a couple of library
  colours may be discontinued on the current UK site (see "not touched" list
  above); nothing was deleted.

## Re-run
```
python tools/harvest_caesarstone.py        # re-scrape (cached; delete tools/_cache/caesarstone to force)
python tools/reconcile_caesarstone.py --report   # dry run, prints the match table
python tools/reconcile_caesarstone.py --apply    # writes images/ + slabs.json
```

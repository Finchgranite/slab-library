# Technistone harvest report (galleries pass)

Source: all 49 library entries already had a good slab main + productUrl
(`https://www.technistone.com/gbr/color/<slug>`) from an earlier pass --
this run is galleries-only.

**Key finding**: an earlier pass had already downloaded a near-complete
media package per colour into OneDrive under
`1. QUARTZ\TECHNISTONE\Sample,slab & kitchen images\<Colour>\`, usually a
`<slug>-mediaPackage-lowRes\` folder with `<slug>-detail.jpg` (closeup),
`<slug>-fullSlab.jpg` (slab, unused -- mains were not replaced),
`<slug>-moodboard.jpg` (styled prop shot, skipped -- not slab/closeup/room),
and `realizations\<slug>-realization-N.jpg` (room/installation photos).
A few colours (Badal Grey, Crystal Diamond, Duna Beige, Elysian Gold,
Mistral White, Taj Mahal Gold) had a flatter layout with `slab-detail.jpg` +
`realization-N.jpg` directly in the colour folder. Every one of the 49 had
at least a room gallery locally; all but Crystal Diamond also had a
closeup. This run therefore used those local originals directly (per
HARVEST-SPEC.md's "check that folder first" rule) rather than re-fetching
images from the live site -- only page TEXT was fetched over the network
(2s/request, cached under `tools/_cache/technistone/`), for the
"<Collection> Collection" subtitle, meta-description blurb and
Specifications-table Finish value used to build `details`.

Up to 2 closeups and 3 rooms were converted per colour (files already on
disk in far greater number for many colours, e.g. Noble Areti Bianco had 46
room candidates locally -- capped to keep the library/contact sheets sane).

## Counts
- Library Technistone engineered entries: 49
- Colours with a local closeup found: 48
- Colours with a local room photo found: 49
- Colours with NEITHER (no gallery material found): 0 -> []
- Closeup images added: 55
- Room images added: 147
- slabSizes filled from price book: 49
- details filled (collection + finish + site blurb): 49
- Mains: unchanged for all 49 (all already had a good slab main; not replaced per task brief)
- Price-book Technistone colours with no library entry: 0 -> []
- Site sitemap slugs with no price-book match (site colours we don't stock): 26
  -> ['ambiente-light', 'calacatta-pastino', 'crystal-anthracite-pure', 'crystal-belgium', 'crystal-calacatta-silva', 'crystal-steel', 'crystal-vulcano', 'decore-ocra', 'gobi-grey', 'imagine-grey', 'metropole-nero', 'noble-botticino', 'noble-imperial-grey', 'noble-linea', 'noble-troya', 'noble-villa', 'pearl-alba', 'pearl-lava', 'pearl-rocca', 'poetic-black', 'romano-ricco', 'starlight-grey', 'starlight-ice', 'taurus-terazzo-black', 'taurus-terazzo-dark', 'taurus-terazzo-grey']
  NOTE: technistone.com/sitemap.xml is dated 2023 and is missing several
  colours whose product pages return 200 today (e.g. badal-grey,
  duna-beige, elysian-gold, morning-daisy, taj-mahal-gold, wedding-lily,
  wild-yucca) -- it is a lower bound, not a full site colour list. The
  OneDrive folder also held originals for further site colours not in our
  price book: Ambiente-Light, Calacatta Pastino, Country Rose, Crystal
  Vulcano, Gobi Grey, Imagine Grey, Romano Ricco, Taurus Terazzo Grey.

## Assumptions
- slabSizes taken from the price book (authoritative per HARVEST-SPEC.md);
  confirmed matching the site's own Specifications "Size" row on Altamonte
  (Jumbo 165: 3300x1650mm both places).
- `details` built as "<Collection> Collection. <Finish> finish.
  <site meta-description>" -- only filled where the field was previously
  absent (all 49, this run).
- Local "moodboard"/"mood board" files (styled prop/flat-lay shots) and
  "*_SLAB*"/"*fullSlab*"/"*-by-Technistone*" files (duplicates of the
  existing main) were excluded from the gallery -- not real closeup/room
  content per the spec's own classifier intent.
- Room photos capped at 3/colour, closeups at 2/colour, picked by natural
  filename order (realizations) / largest-file-first (closeups) -- plenty
  more exist on disk locally for most colours if a deeper gallery is wanted
  later (just re-run harvest_technistone.py with the cap raised).

## Re-run
```
python tools/harvest_technistone.py            # re-scrape page text (cached; delete tools/_cache/technistone to force)
python tools/reconcile_technistone.py --report  # dry run, prints the match table
python tools/reconcile_technistone.py --apply   # writes images/ + slabs.json
```

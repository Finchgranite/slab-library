# Thomas Group (Surfaces Collection) -- Porcelain (Atlas Plan) harvest report

Supplier string: `Thomas Group (Surfaces Collection)` | Material: Porcelain | Brand: Atlas Plan (an Atlas
Concorde brand), sold in the UK exclusively via Thomas Group / The Surface
Collection. Every one of these 76 price-book colours was ABSENT from the
library before this run -- all 76 are new entries.

Primary source: atlasplan.com per-colour pages (`/en/large-format-porcelain-slabs/{slug}/`,
storage.atlasplan.com CDN, curl OK, no bot protection). Colour->slug mapping
was hand-resolved against atlasplan.com's own `/en/large-format-porcelain-slabs/`
index page, which lists every currently-live product slug (66/76 resolved this
way). 7 colours (Calacatta Royal, Concrete Grey, Dolmen Pro Grigio, Kone
Gypsum, Nero Zimbabwe, Statuario Select, White Terrazzo) have no live
atlasplan.com page (direct slug guesses either 404 or soft-redirect to an
unrelated product) but ARE confirmed stocked on thesurfacecollection.co.uk's
single `/products/atlas-plan/` catalogue page, used as fallback (slab photo
only, `lib/photos/{code}.jpg` -- lower resolution than atlasplan.com's own
photography, no closeup/room shots available that way).

3 colours (Carrara Pure, Grigio Intenso, Kone Grey) were NOT resolved on
either site: atlasplan.com's own site search/direct-slug attempts
(carrara-pure, grigio-intenso, kone-grey, kone-gray) all soft-redirect to an
unrelated product page (Bianco Dolomite / Grey Stone / Kone Mix / 404
respectively), and a full-text search of the TSC Atlas Plan catalogue page
found no mention of any of the three. A web search only surfaced third-party
distributor pages (e.g. Gramaco) referencing them with no working
atlasplan.com URL. These 3 are still added as price-book-confirmed library
entries (`image.status: "missing"`, no `productUrl`) since the price book is
the naming authority -- flagging here for a possible manual/browser-driven
follow-up later.

Thicknesses, finishes and `slabSizes` all come from the price book (rounded
mm slab sizes, e.g. `12mm: 3200x1600`), not the site's printed cm sizes
(`162x324` etc) -- consistent with the price book being the sizing authority
per HARVEST-SPEC.md. `details` = `"Atlas Plan · <Look> · <finishes>"` (Look =
the price-book "Price List Section" with the "Atlas Plan - " prefix
stripped), plus the site's one-line meta description where available.

## Counts
- Price-book Porcelain colours (Thomas Group (Surfaces Collection)): 76
- Resolved to a live atlasplan.com product page: 66
- Resolved via thesurfacecollection.co.uk fallback (slab photo only): 7
- Not found on either site: 3 -- ['Carrara Pure', 'Grigio Intenso', 'Kone Grey']
- Library entries added: 76
- Mains (slab) downloaded: 73
- Main download failures: 0
- Mains sourced from a bookmatch crop (no separate full-slab photo existed; `image.status: "closeup-only"`): 2
- Closeup gallery images added: 88
- Room gallery images added: 216
- Entries with no image at all (status "missing"): 3 -- ['Carrara Pure', 'Grigio Intenso', 'Kone Grey']

## Assumptions
- Duplicate-looking price-book colours that are genuinely separate rows
  (`Calacatta Imperial` / `Calacatta Imperiale`, `Taj Mahal` / `Taj Mahal
  (Atlas Plan)`, `Travertine Sand` / `Travertino Sand`) each get their OWN
  library entry pointing at the same underlying atlasplan.com product page --
  the price book, not the site, is the naming authority, and these are kept
  as distinct SKUs/rows rather than merged.
- atlasplan.com's numbered lifestyle photos (`01-...`, `02-...` etc) are
  classified as `room`; the `-bookmatch` slab crop and any filename containing
  "detail"/"texture"/"surface" as `closeup`; the un-suffixed `atlas-plan-epic-
  {slug}-{finish}-{size}-{thickness}mm` file as the main `slab`; a
  `{slug}-warehouse-...` generic photo is always skipped.
- Images: the raw CDN url straight off the live page (a `-clamp_W_H_Q`/
  `-clip_W_H_Q` responsive variant, 960-1920px -- already exceeding the
  library's max_w=1600 webp target) is always used for closeups/rooms since
  it's guaranteed to exist. For the main slab photo only, a quick HEAD check
  is tried first against the unsuffixed "true original" filename (this
  worked for most colours, e.g. Alpinus, Baobab) and falls back to the raw
  CDN variant when that 404s (e.g. Appennino, Calacatta Extra) -- avoids
  wasting slow retry/backoff cycles chasing an original that doesn't exist.

## Re-run
```
python tools/harvest_thomasgroup_porcelain.py                # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_porcelain.py --report      # dry run, prints the add-plan
python tools/reconcile_thomasgroup_porcelain.py --apply       # writes images/ + slabs.json
```

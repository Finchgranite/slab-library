# Thomas Group (Surfaces Collection) -- Porcelain (Atlas Plan) harvest report

Supplier string: `Thomas Group (Surfaces Collection)` | Material: Porcelain | Brand: Atlas Plan (an Atlas
Concorde brand), sold in the UK exclusively via Thomas Group / The Surface
Collection. All 76 price-book colours were ABSENT from the library before the
first run of this script; this pass touched 76 of them
(0 newly added, 76 updated in place -- a repair pass fixing
a slab/room-photo misclassification bug found via the mains contact sheet
after the first apply, see Assumptions).

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
- Library entries added: 0
- Library entries updated in place this pass (repair, see Assumptions): 76
- Mains (slab) downloaded: 73
- Main download failures: 0
- Mains sourced from a bookmatch crop (no separate full-slab photo existed; `image.status: "closeup-only"`): 4
- Closeup gallery images added: 85
- Room gallery images added: 209
- Entries with no image at all (status "missing"): 3 -- ['Carrara Pure', 'Grigio Intenso', 'Kone Grey']

## Assumptions
- Duplicate-looking price-book colours that are genuinely separate rows
  (`Calacatta Imperial` / `Calacatta Imperiale`, `Taj Mahal` / `Taj Mahal
  (Atlas Plan)`, `Travertine Sand` / `Travertino Sand`) each get their OWN
  library entry pointing at the same underlying atlasplan.com product page --
  the price book, not the site, is the naming authority, and these are kept
  as distinct SKUs/rows rather than merged.
- Slab-photo classification is a two-pass, order-independent scan: pass 1
  looks for a filename carrying a printed slab-size token (`162x324`,
  `160x320` etc) without "bookmatch" -- that is always the main `slab`;
  `-bookmatch` filenames are the `closeup` crop (or, for the 2 colours with
  no non-bookmatch size-tagged photo at all -- Calacatta Extra, Statuario
  Supremo -- the first bookmatch crop is promoted to `slab` with
  `image.status: "closeup-only"`). Pass 2 classifies everything left over as
  `closeup`/`room` by weaker filename/alt hints. **Fix (this repair pass):**
  the first apply used a single order-dependent pass whose fallback trusted
  `harvest_lib.classify_kind()`'s bare-word-"slab" filename match -- which
  wrongly picked numbered lifestyle photos as the main slab for a few
  colours (e.g. Appennino's `01-appennino-...-slab-atlas-plan` is actually a
  kitchen photo) whenever they preceded the real size-tagged photo in the
  page's DOM order. Caught via the mains contact sheet, not the numeric
  counts (all of which looked normal) -- **always eyeball
  `thomasgroup-porcelain-mains.png` before trusting a harvest, counts alone
  don't catch a wrong-but-present image.** The two-pass rewrite here fixes
  it for every colour, not just the ones spotted by eye.
- `{slug}-warehouse-...` generic photos are always skipped.
- Closeup/room gallery images use the raw CDN url straight off the live page
  (a `-clamp_W_H_Q`/`-clip_W_H_Q` responsive variant, 960-1920px -- already
  exceeding the library's max_w=1600 webp target, and guaranteed to exist
  since it's literally referenced in the page HTML). Only the main slab photo
  gets a quick HEAD-check upgrade attempt to its unsuffixed "true original"
  filename (succeeds for most colours; falls back to the same raw CDN url,
  no retry cost, when it 404s -- e.g. Appennino's original 404s but its CDN
  variant is still full quality).

## Re-run
```
python tools/harvest_thomasgroup_porcelain.py                # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_porcelain.py --report      # dry run, prints the add-plan
python tools/reconcile_thomasgroup_porcelain.py --apply       # writes images/ + slabs.json
```

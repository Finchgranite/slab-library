# Quartzforms harvest report (galleries pass)

Source: each of the 100 library entries' own stored `productUrl`
(quartzforms.com), fetched directly -- no sitemap crawl needed, all 100 URLs
were already correct. Every product page uses ONE fixed 6-image template
(verified visually against Absolute White + Planet Halley before writing
the classifier): `_slab` (clean full-slab render) / `_gallery01` +
`_gallery02` (real CGI kitchen scenes, wide) / `_gallery03` + `_gallery04`
(styled countertop vignettes with props) / `_detail` (pure texture crop,
no props). This pass took `_detail` as the one closeup and
`_gallery01`+`_gallery02` as up to two rooms; `_gallery03`/`_gallery04`
were skipped as redundant with `_detail`/rooms to keep the request count
sane. `details` built from the page's Collection name + Finishes +
overview paragraph; `slabSizes` from the price book (authority), page
Dimensions table as fallback.

The OneDrive brands folder (`1. QUARTZ\QUARTZFORMS\<Series>\<Colour>`)
already held a large cache of images from an earlier, unfinished pass --
checked first, but NOT used directly: filenames there are inconsistent
(own showroom photos, an AI-mockup or two, legacy site-template exports)
and not reliably auto-classifiable, whereas fetching each colour's own
current page guarantees an accurate, consistent kind label. New downloads
this run go into flat `QUARTZFORMS\<price-book colour name>\` folders
per HARVEST-SPEC (existing `<Series>\<Colour>` folders untouched, not
reorganised).

## Counts
- Library Quartzforms entries: 100
- Page fetch failures: 1 ['Planet Interstellar Gold 2050']
- Mains newly set (was missing): 0
- Mains upgraded (was representative/closeup-only): 1
- Main downloads that failed: 0
- Closeup gallery images added: 99
- Room gallery images added: 104
- Colours with 0 gallery images added (no closeup AND no room slot found): 0 []
- Still not status=slab after this run: ['Planet Interstellar Gold 2050']

## Assumptions
- `_gallery01`/`_gallery02` = room, `_gallery03`/`_gallery04`/`_detail` =
  closeup: derived from actually viewing the downloaded images for 2
  colours (Absolute White, Planet Halley), not guessed from filenames.
  Solid-colour/plain products (e.g. Absolute White) still get 2 room shots
  (generic CGI kitchen renders) even though there's little colour-specific
  content to see in them -- kept anyway since they ARE the site's own
  "room" gallery images for that product.
- Price book remains the sizing authority; site `Dimensions` text used only
  when a colour has no price-book size (shouldn't happen -- all 100
  Quartzforms price-book colours matched 1:1 to library entries).
- Existing 98 "slab" mains were left untouched, only metadata added.

## productUrl fix + confirmed-discontinued colour
- 4 entries had a stale `productUrl` (404): New Era Atlantis 6225, New Era
  Gold 6215, New Era Mystic 6210, New Era Nirvana 6205 -- all stored as
  `.../surfaces/ecotone-new-era-<name>/` (a slug pattern that DOES work for
  the other 8 New Era colours) but these 4 live at `.../surfaces/new-era-<name>/`
  (no `ecotone-` prefix). Corrected in slabs.json via a small patch_library
  call before the main harvest so this run's page fetch could succeed.
- Planet Interstellar Gold 2050 (`image.status: missing`) -- confirmed
  discontinued, not just a bad URL: the stored productUrl 404s, so do
  `interstellar-gold`, `planet-interstellar-gold-2050`, `interstellar-gold-2050`,
  `planet-gold`, and it does not appear in the quartzforms.com surfaces
  listing at all. The OneDrive brands folder's `Planet Series/Interstellar Gold`
  subfolder is also empty (no images from any earlier pass either). Left as
  `missing` -- no real slab face exists to use. Worth asking Quartzforms
  directly if this colour is still available, or removing it from the price
  book if not.

## Re-run
```
python tools/harvest_quartzforms.py             # re-scrape (cached; delete tools/_cache/quartzforms to force)
python tools/reconcile_quartzforms.py --report   # dry run, prints the match table
python tools/reconcile_quartzforms.py --apply    # writes images/ + slabs.json
```

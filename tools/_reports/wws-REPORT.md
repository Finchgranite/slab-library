# World Wide Stones harvest report

Source: `wp-sitemap-posts-page-1.xml` (site's live sitemap endpoint started
404-ing mid-discovery -- a full URL snapshot taken just before that is used
instead, `tools/_cache/wws/_all_urls.txt`; site structure is static WordPress
pages so this is safe) + the `/quartz-slabs/` and `/porcelain-slabs/` index
pages, which are the authority for display name + canonical URL per colour
(several slugs are stale, e.g. `/quartz-slabs/irini-classic/` displays
"Sahara Waves"). 45 of 54 stored productUrls were `www.worldwidestones.co.uk/
?s=...` search-query placeholders, not real pages; all matched colours get
the real product URL from this run.

Each colour page is a bare Elementor page (H1 name, "Slab size: LxWxTmm -
In stock" text, 1-4 photos) with NO consistent slab/closeup/room filename
convention -- classified by filename hint first (few pages: "slab",
"close-up"), then real downloaded-pixel aspect ratio (WWS "slab" photos run
1.3-2.8:1 landscape OR ~0.6-0.85:1 portrait "whole slab stood in the yard"
shots -- both accepted as slab candidates, portrait only when it's the first
photo on the page). The index page's own "*close*"-named thumbnail is always
added as a bonus closeup when found.

## Counts
- Library colours (World Wide Stones, engineered): 54
- Matched to a real site page: 54
- Mains newly set (was missing): 2
- Mains upgraded (was closeup-only): 3
- Main downloads that failed: 0
- Closeup gallery images added: 58
- Room gallery images added: 20
- Still not status=slab after this run: ['Ambient Cemento', 'Borini', 'Calacatta Light', 'Grey Coconut Sparkle', 'Levante Grey', 'New Calacatta Gold', 'Raw Concrete']
- Price-book colours with no site match this run: []
- Extra site products with no price-book match (14):
- `porcelain-slabs/bronze-matte` (https://www.worldwidestones.co.uk/porcelain-slabs/bronze-matte/) -- Bronze -- not in price book
- `porcelain-slabs/reggio-2` (https://www.worldwidestones.co.uk/porcelain-slabs/reggio-2/) -- Techlam Bellagio -- not in price book
- `porcelain-slabs/taj-mahal` (https://www.worldwidestones.co.uk/porcelain-slabs/taj-mahal/) -- Taj Mahal (Porcelain) -- price book HAS a Porcelain Taj Mahal row but the library has no porcelain entry (only the Quartz one) -- reported, not created
- `porcelain-slabs/techlam-bellagio` (https://www.worldwidestones.co.uk/porcelain-slabs/techlam-bellagio/) -- Techlam Alhambra -- not in price book
- `quartz-slabs/amazon-green` (https://www.worldwidestones.co.uk/quartz-slabs/amazon-green/) -- Amazon Green -- not in price book
- `quartz-slabs/ambient-cemento-leathered` (https://www.worldwidestones.co.uk/quartz-slabs/ambient-cemento-leathered/) -- Leathered finish variant -- pb only has Polished
- `quartz-slabs/avalanche-extra` (https://www.worldwidestones.co.uk/quartz-slabs/avalanche-extra/) -- orphaned page, no H1/content
- `quartz-slabs/brooklyn` (https://www.worldwidestones.co.uk/quartz-slabs/brooklyn/) -- Brooklyn "24" -- not in price book (only "25" is)
- `quartz-slabs/calacatta-oro-nuevo` (https://www.worldwidestones.co.uk/quartz-slabs/calacatta-oro-nuevo/) -- Calacatta Oro Nuevo -- orphaned, distinct from Oro Claro
- `quartz-slabs/carrara-y2` (https://www.worldwidestones.co.uk/quartz-slabs/carrara-y2/) -- Carrara Y2 -- not in price book
- `quartz-slabs/cosmic-gold-leather` (https://www.worldwidestones.co.uk/quartz-slabs/cosmic-gold-leather/) -- Leathered finish variant -- pb only has Polished
- `quartz-slabs/golden-flowery` (https://www.worldwidestones.co.uk/quartz-slabs/golden-flowery/) -- Golden Flowery -- not in price book
- `quartz-slabs/patagonia-gris-2` (https://www.worldwidestones.co.uk/quartz-slabs/patagonia-gris-2/) -- Patagonia Gris -- not in price book (site says discontinuing 2026)
- `quartz-slabs/statuary-1st` (https://www.worldwidestones.co.uk/quartz-slabs/statuary-1st/) -- Statuary 1st (Super Jumbo) -- not in price book

## Visual QA pass (important -- read before trusting other suppliers' aspect-only fallback)
WWS embeds "in-situ" kitchen installation photos directly on product pages
with NO filename hint (generic names like `Afyon.jpg`, `Concrete-leather.jpg`,
`Cal-Gold.jpg`) -- the aspect-only classifier fallback cannot tell these apart
from genuine texture closeups, and even the index page's own "*close*"-named
thumbnail was wrong twice (Borini, Crimson Frost: index "close" thumbnail was
actually a full kitchen photo). Two full-page image reviews were done by eye
(`tools/_reports/_wws_review.png` for the 12 target colours,
`_wws_review_all.png` for a sweep of the other 42) before `--apply`:
- 3 of the 12 target gap-fill colours' auto-picked "slab" images were actually
  installation photos and were reverted (Ambient Cemento, Grey Coconut
  Sparkle, Raw Concrete) -- confirmed by full-size view, not just aspect.
  Final new/upgraded mains this run are 5, not the 8 the raw classifier first
  produced: Brooklyn "25", Crimson Frost, New Carrara Frost, Noir St Laurent,
  Sahara Waves.
- ~9 more images (across both target and non-target colours) were moved from
  "closeup" to "room" in the gallery after being visually confirmed as
  installation shots, not texture crops (incl. a post-apply fix on Perla
  Venato's 2nd closeup, done via a follow-up `patch_library` call).
- This was NOT an exhaustive check of all 78 gallery images added -- only
  clear, confidently-identifiable misclassifications were fixed. A further
  visual QA pass on the full `wws-galleries.png` contact sheet would likely
  find a few more room/closeup mislabels (kind tag only, not a wrong main).

## Assumptions to confirm with the supplier
- "Carrara" (pb, 3500x2000 "jumbo" size, distinct from "New Carrara" pb row
  at 3200x1600) matched to `/quartz-slabs/carrara-extra/`, whose H1 is
  "Carrara (Super Jumbo)" -- fits well (size match + naming), treated as
  confirmed rather than a loose guess.
- "Calacatta Oro Frost" (pb, was missing productUrl) matched to site page
  `/quartz-slabs/calacatta-oro-duplicate-941/` which displays as "Calacatta
  Oro Claro" -- name doesn't literally say "Frost"; closest available site
  product by process of elimination (a separate orphaned `calacatta-oro-nuevo`
  page ["Calacatta Oro Nuevo"] also exists and was NOT used). Worth a supplier
  check.
- "New Carrara Frost" (pb) matched to `/quartz-slabs/carrara-frost/`, which
  displays as "Carrara Frost (Shimmer)" -- dropped the site's "New"/kept pb
  naming; token overlap + process of elimination (no plain "Carrara Frost" pb
  row exists).
- "Noir St Laurent" (pb, porcelain, was fully missing) matched to
  `/porcelain-slabs/noir/`, which displays as "Techlam Noir" -- NOT literally
  named "Noir St Laurent" anywhere on site. `/porcelain-slabs/noir-st-laurent/`
  (the slug you'd expect) actually displays "St Laurent" and was used for the
  *other* pb row instead (already had a slab main, confirmed by H1). This pair
  is the least confident match in the run -- please confirm both with WWS.
- Porcelain "Taj Mahal": the price book has a distinct Porcelain Taj Mahal row
  (Matt finish) separate from the Quartz Taj Mahal row, and the site confirms
  a real `/porcelain-slabs/taj-mahal/` page -- but the library only has ONE
  "Taj Mahal" entry (material Quartz). No new entry was created this run
  (out of scope per this job's fixed 54-entry brief); flagging for the
  orchestrator to decide whether to add a Porcelain Taj Mahal entry.
- `slabSizes` always taken from the price book, not the site's own "Slab
  size:" text (price book had every colour/thickness covered already).

## Site products confirmed NOT in our price book (no entry created)
14 extra ranges/variants -- see list above. Notable:
Techlam Alhambra/Bellagio/Bronze (whole extra Techlam sub-lines), several
"Super Jumbo"/"Extra"/"Y2"/"Nuevo" size-variant duplicate pages for colours
we already stock in the standard size, and Patagonia Gris (site says
"discontinuing in 2026").

## Re-run
```
python tools/harvest_wws.py             # re-scrape (cached; delete tools/_cache/wws to force)
python tools/reconcile_wws.py --report  # dry run, prints the match table
python tools/reconcile_wws.py --apply   # writes images/ + slabs.json
```

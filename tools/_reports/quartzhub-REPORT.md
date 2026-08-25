# Quartz Hub harvest report

Source: https://www.quartzhub.co.uk/sitemap.xml -> every sub-sitemap fetched
(home/posts/pages/categories/tags/archives). Confirmed the site has NO
per-colour product pages at all -- sitemap-pages.xml lists exactly 5 pages
(home, /gallery/, /about-us/, /our-services/, /faq/). All colour photography
lives in one Modula lightbox gallery at /gallery/, which is now every entry's
`productUrl` (replacing the 14 `?s=...` WordPress search-query placeholders
and Arabescatta Oro's empty productUrl -- 15 URLs fixed in total).

Gallery items expose a clean `data-caption`/`alt` colour name and the true
original `data-full` URL + width/height directly in the HTML (no filename
guessing or HEAD requests needed). Per colour: a landscape "main" photo and
either a perfectly square 2560x2560 crop (10 older colours) or a
`*-swatch-image-*` detail crop (Taj Mahal, Arabescatta Oro, the 4 Ceramic
colours, Onyx Crema) -- both classified "closeup" by `hl.classify_kind`
(square aspect / "swatch" keyword). Onyx Crema alone has a 3rd photo, a
backlit translucency shot (caption "... - Backlit"), classified "room" by a
one-off keyword override (no kitchen/cabinets photo exists on the whole
site, so this is the closest thing to an in-use photo Quartz Hub has for any
colour).

## Counts
- Site colours found (gallery + home/about-us/our-services/faq checked): 14
- Price-book Quartz Hub colours: 15
- Library entries (all engineered, all Quartz Hub): 15
- productUrls fixed (placeholder/empty -> real https://www.quartzhub.co.uk/gallery/): 15
- Mains upgraded (closeup-only -> slab): 1 -- Onyx Crema only, per task brief (the
  other 14 mains were already good "slab" photos and were deliberately left untouched)
- Closeup gallery images added: 14
- Room gallery images added: 1
- slabSizes/details filled from the price book (site has no spec text at all): 15
- Site colour with real photos but no price-book/library row: ['Ultra White Shimmer'] --
  "Ultra White Shimmer" (2 photos, same 2024/08 batch as Black Marquina etc.) -- an extra Quartz
  Hub quartz colour we evidently don't currently stock; no entry invented for it.
- Price-book/library colour with NO site photo anywhere: ['Laurent'] -- "Laurent" (Ceramic).
  productUrl/slabSizes/details still filled (real gallery page + price book), but no image
  could be added -- ask Quartz Hub whether Laurent has been discontinued or just never
  photographed for the current site.

## Assumptions
- "DO NOT replace the 14 good mains" (task brief) takes precedence over the general
  HARVEST-SPEC default of always fetching the best available main -- even though every one of
  those 13 non-Onyx-Crema colours also has a landscape site photo, it is deliberately never
  picked up as a "slab" kind here (see harvest_quartzhub.py docstring: those photos are <1.8:1
  aspect and carry no slab-hinting filename/keyword, so `hl.classify_kind` naturally returns
  None for them and they are simply not in the harvest manifest).
- `details` is built purely from the price book (material + finish + thickness) because the
  live site carries zero per-colour spec/blurb text anywhere (gallery/home/about-us/
  our-services/faq all checked) -- only photos.
- Onyx Crema's new main is the gallery's own "1.Onyx-Creame-30mm-and-20mm.jpg", 2387x1204
  (1.98:1) -- a genuine full-slab photo, not a crop.

## Re-run
```
python tools/harvest_quartzhub.py             # re-scrape (cached; delete tools/_cache/quartzhub to force)
python tools/reconcile_quartzhub.py --report   # dry run, prints the match table
python tools/reconcile_quartzhub.py --apply    # writes images/ + slabs.json
```

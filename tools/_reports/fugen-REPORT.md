# Fugen harvest report

Source: https://fugenstone.co.uk/product-sitemap.xml -> product-sitemap (59
`/quartz-worktops/` colour pages; porcelain pages excluded, no porcelain in our
46-entry Fugen scope). Real product domain is `fugenstone.co.uk` (no `www`) --
the `www.fugenstone.co.uk/?s=...` search-query URLs previously stored as
`productUrl` on ~33 entries were placeholders, not real product pages; this
run replaces them with the real WooCommerce product URL for every matched
colour.

Main slab image: every page carries a filename containing "slab" under an
"Entire Slab"/"Entire slab" heading (2:1 aspect), separate from the
WooCommerce product gallery. Close-ups: "*Tile*" / old-template
"441_FUGENSTONE_*"/"..._R.jpg" / unnumbered "*Gallery*"/"*Gallery-1*".
Rooms: "*Gallery-2*"/"*Gallery-3*" (numbered >=2) / "*Set-N*". Styled
flat-lay mood-board shots ("*-comp.jpg", "Beth-Davis...Flatlays...") are
skipped -- verified visually, not real slab/closeup/room content.

## Counts
(from the `--apply` run that actually downloaded/wrote images; a second
`--apply` was run afterwards only to fix a description-decoding bug, see
Assumptions -- it re-filled metadata but re-used the already-cached images,
so its own delta counts read as 0/90/12 leftover-cache reuse, not fresh work)
- Site `/quartz-worktops/` pages: 59 (fetch failures: 0)
- Site pages with a slab image found: 52
- Library rows matched (finish-variant colours count once per row): 45
- Mains newly set (was missing -> slab): 11 -- Celestial Leather, Celestial
  Polished, Imperium Leather, Imperium Polished, Jasper Leather, Jasper
  Polished, Marfil Luxe Leather, Matrix Leather, Niagara, Roma Leather,
  Roma Polished
- Mains upgraded (was closeup-only): 0
- Main downloads that failed: 0
- Closeup gallery images added: 90 (up to 2 per matched colour)
- Room gallery images added: 12
- Library Fugen engineered colours not touched this run (no site match): ['Light Grey']
- Price-book Fugen engineered colours still unfilled: ['Light Grey']
- Site products with no library/price-book claim (Fugen ranges we don't currently stock): 19 -- ['Aurora Wave', 'Calacatta Royal', 'Dark Grey', 'Desert Salt', 'Dune Frost', 'Euphrates', 'Gilded Chalk', 'Gris De Savoie', 'Juniper', 'Memory', 'Moon Lace', 'Noor', 'Pietra Grey', 'Platinum', 'Soft Day', 'Sunbeams', 'Superior Calacatta', 'Supernova', 'Whisper Ash']
- Still not status=slab after this run: ['Cotswold Gold', 'Light Grey', 'Silver Drift']

## Assumptions
- Finish-variant price-book rows ("X Leather"/"X Polished"/"Jasper Leather"+
  "Jasper Polished") map to ONE Fugen product page; the WooCommerce
  `data-product_variations` image is identical across finishes on every
  product checked (verified on Celestial) so both/all rows get the same
  slab/closeup/room images, `details` states each row's own finish.
- Site finish wording sometimes differs from our price-book finish word --
  e.g. Imperium's page says "Polished and Satin" (not "Leather"); Jasper's
  page says "Polished or Satin" (not "Leather"). Treated as the same
  Leather<->Satin low-sheen finish family per colour so "Imperium Leather"/
  "Jasper Leather" still map to this product -- worth confirming with Fugen
  whether their "Leather" SKUs are literally labelled "Satin" on the current
  site, or a genuinely different finish.
- "Light Grey" (price book, Polished): no matching product on the site --
  only "Dark Grey" exists, no mention of "Light Grey" anywhere on that page.
  Likely renamed/discontinued online. Still `missing`; ask Fugen.
- Niagara site page states slab size "3200 x 1260 mm" (odd width vs the
  price book's 3200x1600) -- price book size kept as authority per the
  existing sizing rule, site figure ignored as a likely site typo.
- Price book remains the sizing/naming authority; `slabSizes` from price book
  first, the page's parsed "LxW mm" text only as a fallback.
- 7 pages have an empty "Entire Slab" image widget (no asset uploaded):
  Black Shimmer, Silver Drift, Cotswold Gold, Valley White, Dune Frost,
  Gilded Chalk, Sunbeams -- of these, Black Shimmer/Silver Drift/
  Cotswold Gold/Valley White are in our library; metadata (productUrl,
  slabSizes, details, closeups) still filled where matched, but their main
  image is unchanged (Black Shimmer/Valley White already had a good "slab"
  main; Silver Drift/Cotswold Gold remain "closeup-only" -- the site itself
  has no slab photo for them).

## Re-run
```
python tools/harvest_fugen.py            # re-scrape (cached; delete tools/_cache/fugen to force)
python tools/reconcile_fugen.py --report  # dry run, prints the match table
python tools/reconcile_fugen.py --apply   # writes images/ + slabs.json
```

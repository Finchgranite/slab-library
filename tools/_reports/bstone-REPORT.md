# B-Stone harvest report

Source: bstoneuk.co.uk has NO per-colour product pages. Every BQuartz colour is
one lightbox tile on `https://bstoneuk.co.uk/material/bquartz/` (25 tiles);
every Techlam (sintered stone) colour one tile on
`https://bstoneuk.co.uk/material/techlam/` (12 tiles). Each tile's full-res
`href` is the true slab photo (verified ~2:1 aspect, e.g. 2560x1280,
1920x960) -- not a swatch. `productUrl` for every matched colour is therefore
that shared listing page; there is nothing more specific to link to. No
texture/closeup imagery exists anywhere on the site for either material.

Room/kitchen photos come from a separate post type: `/inspiration-sitemap.xml`
lists individual project posts, many slugged `bquartz-<colour>[-N]` (matched
via `harvest_lib.match_colour`). No Techlam/sintered inspiration posts exist.
Up to 2 posts per BQuartz colour were fetched, 1 photo taken from each.

## Counts
- Site engineered tiles: 37 (25 BQuartz + 12 Techlam)
- Library/price-book colours matched or created: 35
- New entries created (site+price-book confirmed, no prior library row): 4 -- ['Cadiz', 'Colossal Cream', 'Forest', 'Salina Ivory']
- Mains newly set (was missing/new): 8
- Mains upgraded (was closeup-only/representative): 2
- Room gallery images added: 26
- Metadata-only fills (productUrl/slabSizes/details) on rows whose main was kept: 25
- Library B-Stone engineered colours the site has no matching tile for (untouched): ['Bianco Bello']
- Site engineered tiles with no library/price-book claim (extra B-Stone ranges we don't stock): 2 -- ['Sintered Stone:FIOR DI BOSCO MATT - 3200x1600mm', 'Sintered Stone:TAJ MAHAL MATT - 3200x1600x20mm - stock colour']
- Still not status=slab after this run: []

## Assumptions
- `productUrl` = the shared bquartz/techlam listing page for every matched
  colour (site has no deeper per-colour URL structure to link to).
- BQuartz "polished" is the library's implicit default (no "polished" suffix
  in our colour names) so it is stripped when matching; "matt" IS kept
  because our library genuinely holds separate "X matt" entries. Techlam
  finish words (Matt/3D Textured) are always stripped -- our sintered colour
  names never carry a finish suffix; finish is recorded in `details` instead.
- Cadiz (BQuartz) is explicitly captioned "NEW (arriving end of August 2026)"
  on the site and confirmed by the price book (`_pb_missing.json`, stock=No)
  -- created with a real slab photo despite not yet being in stock.
- Colossal Cream, Forest, Salina Ivory (Techlam) are on the site and in the
  price book's missing list -- created.
- "Bianco Bello" (library BQuartz colour) has no matching tile on the current
  bquartz page -- left untouched (existing slab image kept), reported above;
  may be discontinued on the supplier's site or renamed.
- "Fior Di Bosco" and "Taj Mahal" (Techlam tiles) are not in the price book
  under any B-Stone row and have no library entry -- not created per the
  "only create entries the price book confirms" rule; reported as extra
  ranges we don't currently stock.
- No closeup/texture imagery exists anywhere on bstoneuk.co.uk for either
  material -- 0 closeups added (not a gap in this harvest, a gap on the
  supplier's site).
- Room photos exist only for BQuartz (17 of 25 matched colours had at least
  one `/inspiration/bquartz-*` post); Techlam/sintered colours have none.
- Price book remains the sizing authority; `slabSizes` from
  `hl.load_pricebook("B-Stone")` where available.

## Re-run
```
python tools/harvest_bstone.py             # re-scrape (cached; delete tools/_cache/bstone to force)
python tools/reconcile_bstone.py --report   # dry run, prints the match table
python tools/reconcile_bstone.py --apply    # writes images/ + slabs.json
```

# Lumina Stone harvest report

No authoritative UK site (orchestrator-relaxed source rule, see HARVEST-SPEC.md
JOB brief). Two sources used:
- **pisastone.co.uk/quartz-worktops/lumina-stone** -- single reseller page, 16
  UK-stocked colours, one photo + 4-digit SKU each (RSC JSON payload, not
  plain `<img>` tags). **Correction to the earlier discovery note**: checked
  all 16 photos at full resolution -- 15 are CGI kitchen-installation renders
  (~1.3-1.6:1), not slab-face photos, so they were used as `room` gallery
  images, not mains. Only Maya (skuCode 8313) is a genuine flat macro-texture
  crop, used as a `closeup`. No per-colour URL exists on this site -- these
  16 colours' `productUrl` is the shared page unless luminastone.eu (below)
  had a better per-colour one.
- **luminastone.eu** (brand's own WordPress site) -- current catalogue has
  moved to a refreshed colour range; a full portfolio-sitemap sweep (34
  slugs) found 5 genuine cross-matches with real per-colour pages: Sand Swan,
  White Swan, White Sand (all 3 already had good library mains -- gallery
  only), **Soapstone** and **Urban Cemento** (both `missing` -> real slab-face
  photo found, ~2.0:1, matches the price book's 3200x1600 slab size).
  "Cemento Urban" on the site matched price book "Urban Cemento" by reversed
  word order.

## Counts
- Library Lumina Stone colours: 18
- Mains newly set to "slab" (was missing): 2 (Soapstone, Urban Cemento)
- Mains promoted "missing" -> "closeup-only": 1 (Maya)
- Existing "slab" mains left untouched (Belvedere, Coral Metro, Coral Naturale,
  Sand Swan, White Sand, White Swan): 6
- Existing "closeup-only" left untouched (Patagonia -- only image found is a
  room render, not a slab face): 1
- Closeup gallery images added: 5
- Room gallery images added: 19
- Main image download failures: 0
- Still `missing` after this run, 7: ['Astral White', 'Bianco Venatino', 'Calacatta Eternal', 'Statuario Frost', 'Statuario Rhin', 'Statuario Venato', 'Super White Marble']
- Not found in EITHER source, 1: ['Bronze Cascade']

## Colours to ask Granite Granite Ltd about (importer, Basildon)
- **Bronze Cascade** -- not on pisastone's 16 UK-stocked colours, not on
  luminastone.eu's 34 portfolio slugs. granitewarehouseyork.co.uk (4th
  reseller named in the discovery) now returns "Account Suspended" (dead
  hosting, retried this pass with `curl -k`) -- no further web source to try.
- Urban Cemento is now resolved (see above) so only Bronze Cascade remains
  genuinely unsourced.

## Assumptions
- `slabSizes` = price book (3200x1600, 20/30mm, all 18 colours) -- no page
  contradicted this.
- `details` = "Lumina Stone quartz worktop · <Finish> finish" from the price
  book's own Finish column (Polished / S-Tech & Nano / Silica-Free / Polished
  & S-Tech per colour).
- Soapstone's and Urban Cemento's new slab mains are CGI renders (filenames
  say "-3D-"/product-shot style, not phone-camera photos) -- `image.scale`
  set to "approx" (no stated true mm on the page, but aspect matches the
  price-book 3200x1600 ratio closely).
- Urban Cemento's room-shot images on luminastone.eu were **excluded** --
  their own filenames are tagged "...FakeIA-..." (the site's own admission
  they are AI-generated marketing images, not real photography/CGI of the
  actual product).
- Patagonia's only pisastone image is a kitchen room render (dramatic
  black/gold veining) -- added as a `room` gallery image but NOT used to
  promote the existing `closeup-only` main to `slab` (it is not a slab face).
- Astral White, Bianco Venatino, Calacatta Eternal, Statuario Frost/Rhin/
  Venato, Super White Marble: only image found on either source is a pisastone
  kitchen room render -- `productUrl` + `room` gallery image added, main
  correctly left `missing` (no slab-face photo exists for these on the web
  this pass).

## Re-run
```
python tools/harvest_lumina.py           # re-scrape (cached; delete tools/_cache/lumina to force)
python tools/reconcile_lumina.py --report   # dry run, prints the match table
python tools/reconcile_lumina.py --apply    # writes images/ + slabs.json
```

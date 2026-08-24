# Picasso Surfaces harvest report

Source: www.picassostones.com (WordPress/Elementor). No product sitemap and no
per-colour product pages exist -- colours live only as images inside five
"series" gallery pages (marble/designer/mirror/plain/stellar) plus an
aggregate "our-products" grid and a "gallery" room-shot page. The open WP
REST API (`/wp-json/wp/v2/media`, 390 items) was used as the source of truth
for true image originals/dimensions and each image's auto-generated
permalink (used as `productUrl`, e.g. .../aspen, .../celestial-gold) --
richer than scraping <img> tags per HARVEST-SPEC lesson (b). No closeup/
texture photos exist anywhere on the site (checked media titles for
swatch/texture/detail/zoom/sample -- none found).

## Counts
- Site colours found (our-products + 5 series pages, deduped): 36
- Matched to existing library entries: 23
- New library entries added (price-book confirmed, none needed): 0
- Mains newly set (was missing -> slab): 1 (Grey Mirror)
- Mains upgraded (was closeup-only -> slab): 1 (Black Mirror)
- Main downloads that failed: 0
- Room gallery images added: 16 (site has no closeup/texture shots)
- Unmatched site colours (site sells, we don't stock under Picasso): 13 -- ['Calacatta Luxe', 'Calacatta Nero', 'Calacatta Vista', 'Cararra Rhythm', 'Carrara', 'Carrara Rhythm', 'Carrara Rhythm white', 'Celestial Black', 'Silver Cloud', 'Statuario', 'Statuario Gold', 'Statuario Modern', 'White Stellar']
- Unmatched price-book Picasso colours (not on current live site): 22 -- ['Annapurna', 'Arabescato Creme', 'Aspen Gold', 'Cashmere', 'Cristallo', 'Erebus', 'Golden Storm', 'Golden Thunder Shimmer', 'Himalyan Pink Onyx', 'Jade Glacia', 'Nacorado', 'Opal Royale', 'Orella', 'Patagonia', 'Pearla', 'Solarius', 'Taj Honey Onyx', 'Taj Mahal Extra', 'Tuscan', 'Verde Onyx', 'Verde Tempsta', 'Viola']
- Library Picasso colours still not `slab` after this run: ['Cashmere', 'Cristallo', 'Erebus', 'Himalyan Pink Onyx', 'Jade Glacia', 'Nacorado', 'Opal Royale', 'Orella', 'Patagonia', 'Pearla', 'Solarius', 'Taj Honey Onyx', 'Tuscan', 'Verde Onyx', 'Verde Tempsta', 'Viola']

## Assumptions / notes
- `productUrl` = each image's own WP-generated attachment permalink (from
  the REST media record's `link`), which is the most specific page the site
  offers per colour -- there is no real product page.
- `slabSizes` comes from the price book (all Picasso colours: 3200x1600mm,
  20mm and 30mm) -- the site states no dimensions itself.
- `details` = "Picasso · <Series> · <Finish(es)>" using the price-book
  Finish column (falls back to "Polished" where absent).
- **Golden Thunder / Thunder Gold** are the same physical colour (price book:
  "Golden Thunder (aka Thunder Gold)"). Harvested into "Golden Thunder" only;
  "Thunder Gold" then had its `image`/`images`/`productUrl` overwritten to
  mirror Golden Thunder's so both entries show the identical photo. Neither
  entry was deleted (per orchestrator instruction -- merge happens later).
- Existing `image.status == "slab"` mains were left untouched even where the
  site now has a higher-resolution original (e.g. Aqua Gold, Arctic Storm,
  Calacatta Gold) -- only productUrl/slabSizes/details/room-gallery were
  added for those, per HARVEST-SPEC rule 8/reconcile convention.
- 16 of the 17 previously-`missing` colours are still missing: the live site
  genuinely has no page/image for Annapurna, Aqua Gold [already slab --
  n/a], Cashmere, Cristallo, Erebus, Golden Storm, Golden Thunder Shimmer,
  Himalyan Pink Onyx, Jade Glacia, Nacorado, Opal Royale, Orella, Patagonia,
  Pearla, Solarius, Taj Honey Onyx, Tuscan, Verde Onyx, Verde Tempsta, Viola
  (checked via the full 390-item media library, not just the linked pages --
  no matching filenames/titles exist at all). Only **Grey Mirror** was
  recoverable (site: "Dark Grey Mirror" under Mirror Series). **Black
  Mirror** (was closeup-only) was upgraded to a real slab photo too.
- Unmatched site colours (Statuario/Statuario Gold/Statuario Modern,
  Calacatta Vista/Luxe/Nero, Carrara/Carrara Rhythm, Celestial Black, Silver
  Cloud, White Stellar) are real Picasso Stones products but not in Finch's
  price book under this supplier -- not invented as new entries.

## Re-run
```
python tools/harvest_picasso.py         # re-scrape (cached; delete tools/_cache/picasso to force)
python tools/reconcile_picasso.py --report   # dry run, prints the match table
python tools/reconcile_picasso.py --apply    # writes images/ + slabs.json
```

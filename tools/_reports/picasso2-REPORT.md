# Picasso Surfaces harvest report -- NEW site (picassosurfaces.co.uk)

Source: https://picassosurfaces.co.uk/wp-sitemap-posts-product-1.xml -- 40 product
pages: 36 real colours + 4 "Symphony ... HD Print" pages (a new HD-print range,
not in the price book -- listed below, NOT added as library entries). The
sitemap XML itself is served with a WordPress "soft 404" HTTP status despite a
valid body (harvest script fetches it with plain curl, no -f, to work around
that); every product page itself returns a normal 200.

Supersedes `harvest_picasso.py`/`reconcile_picasso.py`, which harvested the
OLD site (picassostones.com) last night -- that site is now gone from the
supplier's canonical links; all `productUrl`s here point at the new site.

Every product page has exactly one Elementor "gallery.default" widget (NOT a
standard WooCommerce gallery) holding 1-4 images, all served at a uniform
~1920x1200 (1.6:1) crop regardless of whether the shot is a full slab, a
texture close-up, or a room photo -- so aspect ratio carries no kind signal
on this site (unlike Fugen/Compac). All 102 gallery images across the 36
colour pages were downloaded and visually classified by hand from contact
sheets (`tools/_cache/picasso2/preview_part[123].png`) before writing
`reconcile_picasso2.py`'s PICKS table -- see that file's docstring for the
full reasoning, including two site data-quality issues found along the way
(Celestial Grey/White share identical photo URLs; Taj Honey Onyx and Verde
Onyx each carry a dramatic backlit "onyx-glow" shot that was skipped in
favour of the true-colour studio shot for `image`).

Each page's `<meta name="description">` cleanly contains the marketing blurb
plus a fixed "Slab size available / thickness available / finish(es)
available" block -- used directly for `details`/`slabSizes` (falling back to
the price book only if a page's fields don't parse).

## Counts
- Site colour pages: 36 (Symphony HD-print pages, not added: 4 -- ['https://picassosurfaces.co.uk/product/symphony-ice-age-matte-finish-hd-print/', 'https://picassosurfaces.co.uk/product/symphony-taj-mahal-hd-print/', 'https://picassosurfaces.co.uk/product/symphony-water-shadow-hd-print/', 'https://picassosurfaces.co.uk/product/symphony-winter-field-hd-print/'])
- Library Picasso Surfaces engineered colours touched this run: 37 / 46
- Mains newly set (was missing -> slab): 13 (Cashmere, Cristallo, Erebus, Himalyan Pink Onyx,
  Jade Glacia, Nacorado, Opal Royale, Orella, Patagonia, Pearla, Solarius, Taj Honey Onyx, Verde Onyx)
- Mains upgraded (was closeup-only -> slab): 0
- Main downloads that failed: 0
- Closeup gallery images added: 32
- Room gallery images added: 39
  (counts from the apply run that did the work; a later --apply re-run to fix a report-writer
  bug found everything already `kept`/present, which is expected and correct)
- Still not status=slab after this run: ['Tuscan', 'Verde Tempsta', 'Viola']
- Library colours confirmed present with a slab image, but NOT on the new site
  (ask Carl -- old-site-only or discontinued?): ['Black Mirror', 'Calacatta Gold', 'Carrara Gold', 'Golden Thunder Shimmer', 'Grey Mirror', 'White Mirror']
- Library colours the site has no page for at all: ['Tuscan', 'Verde Tempsta', 'Viola']

## Assumptions
- Cristallo and Erebus have no plinth/rack "whole slab" studio photo on their
  page -- their best full-bleed texture crop was promoted to `image` instead
  (still a real, in-focus, whole-pattern shot at normal viewing scale, not a
  macro grain zoom -- just not standing on a plinth). Worth asking Carl for a
  proper slab photo of these two specifically.
- Taj Honey Onyx image #3 and Cristallo image #1 were excluded entirely (both
  look implausibly pale/mismatched next to every other image on the same
  page -- possible copy-paste error on the supplier's site).
- Verde Onyx and Taj Honey Onyx each have a dramatic backlit "onyx-glow" shot
  (Verde Onyx's glows amber/gold, not green) -- skipped in favour of the
  true-colour daylight studio shot for `image`; the backlit shot was not
  added to the gallery either, to keep the set unambiguous.
- Celestial Grey and Celestial White's pages embed byte-identical image URLs.
  Applied to Celestial White only (both the "cw" filename prefix and page
  name point that way); Celestial Grey's existing main/gallery are untouched
  this run. Ask Carl which product the 3 photos actually belong to.
- `slabSizes`/finish come from each page's own stated text first (all 36
  checked state "3200x1600mm, 20mm and 30mm" except Arabescato Creme, which
  states "Polished and Matte" finishes), price book only as fallback.
- Golden Thunder's page/photos apply to both the "Golden Thunder" and
  "Thunder Gold" price-book rows (pre-existing alias pairing, unchanged).

## Re-run
```
python tools/harvest_picasso2.py             # re-scrape (cached; delete tools/_cache/picasso2 to force)
python tools/reconcile_picasso2.py --report   # dry run, prints the match table
python tools/reconcile_picasso2.py --apply    # writes images/ + slabs.json
```

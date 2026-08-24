# UK Stone Company harvest report

Source: https://ukstonecompany.com (WordPress/WooCommerce/Avada). Colour list
came from `wp-sitemap-posts-product-1.xml` (273 product pages total, natural
stone -- granite/marble/quartzite -- excluded, out of scope this phase).
Each targeted product page has exactly ONE hero photo (no closeup/room
galleries anywhere on the site); it lives in the
`woocommerce-product-gallery__wrapper` figure as `data-large_image` (true px
size in `data-large_image_width/height`), alongside a `custom-attributes`
list (Material Finishes / Material Type / Quartz Sizes / Thickness / Sizes in
metres) and a `Category:` line used to reject natural-stone pages that share
a colour word (see Rejected below).

Because the site's title/slug naming is irregular (some titles fold in
"Jumbo"/"Super Jumbo" as a size descriptor, some finish variants collapse
onto one product page, one dark/light pair never got a Light page), matching
was done by hand (`harvest_ukstone.py`'s `TARGETS` dict, 42 site pages) built
from the sitemap's 273 slugs cross-checked against the 54 price-book colours,
rather than the generic token-subset matcher.

## Counts
- Library colours (price book "UK Stone Company"): 54
- Site pages targeted / matched: 42
- Mains newly set to "slab" (was missing/closeup-only): 11
- Mains set to "closeup-only" (best image found is a texture crop, not a full slab): 2
- Mains set to "representative" (borrowed image, see Assumptions): 2
- Main downloads that failed: 0
- Existing "slab" mains left untouched, productUrl/slabSizes/details filled: 27
- Closeup/room gallery images: 0 (site has none -- single hero image per product)
- Still `missing` (no site page found for this price-book colour), 12: ['Arabescato Porto', 'Blanco Carrara Extra', 'Blanco Luna', 'Blanco Shimmer', 'Calacatta Amber Oro', 'Calacatta Naple', 'Calacatta Oro', 'Concrete', 'Concrete Light', 'Emerald Green Translucent', 'Grey Shimmer Light', 'Mystic Rivers']
- Unmatched site products investigated and rejected (not this colour), 3:
  - krystallus-translucent: Krystallo Translucent Polished Quartzite 2cm -- category Quartzite (natural stone), not the pricebook's Emerald Green Translucent quartz
  - moon-white: Moon White Polished Granite 3cm -- category Granite (natural stone, Colour=Black per its own attribute), not the pricebook's Blanco Luna
  - mystic-waters-super-jumbo-quartz-2cm: "Mystic Waters" (category Quartz) -- name does not match pricebook's "Mystic Rivers"; not assumed the same product

## Assumptions / judgement calls
- **Grey Shimmer Dark vs Light**: the site carries only one "Grey Shimmer"
  product (no Dark/Light split in the slug or title); its photo reads as a
  mid/dark tone, so it was assigned to "Grey Shimmer Dark". "Grey Shimmer
  Light" stays `missing`. Worth a supplier check.
- **Carrara Vincenza**: site title is "Blanco Carrara Vincenza Jumbo Quartz"
  -- token-subset matching would reject this (extra "Blanco" token) so it was
  matched by hand to the price book's "Carrara Vincenza".
- **Highlands Polished/Leathered/Shimmer Polished**: the site serves the
  exact same file for all three finish variants' product pages. Polished
  (the plain/default finish this generic photo most plausibly shows) got
  `status: slab`; the other two got `status: representative` with
  `borrowedFrom` noted -- a real texture-specific photo would be better if
  the supplier can provide one.
- **Grey Mirror Dark/Light**: only image available (2020 upload, filenames
  "23-e.jpg"/"24-e2.jpg") is a cropped texture swatch on white padding, not a
  full slab -- promoted `missing -> closeup-only` (matching how the library
  already treated Blanco Lustre before this run), not `slab`.
- `slabSizes` comes from the price book first; the page's own `Sizes`
  attribute (metres, converted to mm) only as a fallback when the price book
  has no size row for that colour+thickness.
- `details` = "UK Stone Company Quartz · <Material Finishes> finish · <Quartz
  Sizes> format" from the page's own attributes. No distributor/other-brand
  name was found anywhere on any fetched page (no description/tab content,
  no brand text) -- these appear to be UK Stone Company's own-labelled range
  (product photos carry a "UK STONE COMPANY" logo watermark), so no brand
  prefix was added to `details`.
- No closeup/room gallery images exist anywhere on this site -- every product
  page has exactly one image in its WooCommerce gallery.

## Re-run
```
python tools/harvest_ukstone.py                 # re-scrape (cached; delete tools/_cache/ukstone to force)
python tools/reconcile_ukstone.py --report       # dry run, prints the match table
python tools/reconcile_ukstone.py --apply        # writes images/ + slabs.json
```

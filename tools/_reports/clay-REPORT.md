# Clay International gallery harvest report

Source: images ALREADY downloaded by the phase-1 `tools/clay_harvest.py` crawl into
OneDrive `3. CERAMIC- PORCELAIN/Infinity porcelain - clay international/<Colour>/`
(one folder per colour, populated from each product page's own WooCommerce gallery).
This run classifies what's already there rather than re-fetching -- confirmed via the
live `product-sitemap.xml` (72 URLs) that nothing new has been added to the 6 colours
whose folder only ever held the single product-master image (see below), so no
network re-fetch was needed for this pass.

## Counts
- Clay International library entries: 78
- Matched to a folder and processed: 75
- Not on the live site (no productUrl, no gallery possible): 3 -- ['Antibes', 'Bercy', 'Gordes']
- Closeup images added: 53
- Room images added: 69
- Colours with a room but no closeup candidate: 16 -- ['Absolute Black', 'Calacatta Glory', 'Extra Statuario', 'Fossil', 'Fossil Row', 'Fossil Tartan', 'Plaster Ash', 'Plaster Bone', 'Plaster Ground', 'Plaster Sand', 'Plaster Snow', 'Plaster Warm', 'Sandstone Gray', 'Sandstone Light', 'Sandstone Silver', 'Sandstone Warm']
- Colours with NO gallery candidates at all (main-only, confirmed against the live
  page too): 6 -- ['Chianca Di Ostuni', 'Milan Stone', 'Pulpis Brown', 'Terrazzo White', 'Total Grey', 'Total White']
- Vein Tech rows (productUrl/slabSizes/details filled, reusing the base colour's
  photos): Calacatta Hermitage Vein Tech, Calacatta Magnifico Vein Tech, Statuario
  Principe Vein Tech
- Mains: unchanged (75 already `slab`, 3 still `missing` -- see below)

## Assumptions
- Filename origin story: OneDrive folder contents were literally scraped from each
  colour's own `data-large_image` WooCommerce gallery links, however oddly named
  (Italian marketing terms, WhatsApp exports, batch "Screenshot-2025-02-10-*"
  captures, phone "original-<GUID>" exports) -- spot-checked ~15 images across
  colours to confirm they are genuine, colour-appropriate site photography, not
  swatches or unrelated colours reused by mistake.
- Classification: keyword hints first (bagno/cucina/dining/ambiente/living/install
  -> room; dettaglio/detail/thumb/texture -> closeup), then a position fallback for
  unlabelled numbered extras (first -> room, second -> closeup). No aspect-ratio
  signal was reliable on this dataset (both room and closeup shots run ~1.4-2.0:1
  here) -- verified visually before relying on the fallback.
- Any image file whose name exactly matches the current main's own source basename
  is excluded from gallery candidates (same file as the main, not new content) --
  this mattered most for the Arkeon range (Fossil/Plaster/Sandstone), Buxy Select,
  Verde France, Travertine Grey, where the site reuses the main's filename inside
  the product's own gallery listing too.
- Antibes, Bercy, Gordes: confirmed absent from `product-sitemap.xml` (72 URLs) and
  from a site search for each name -- not currently sold on clayinternational.co.uk.
  Left `missing`, no productUrl added; cannot fabricate a slab face. Worth asking
  Clay International directly whether these 3 Infinity colours were discontinued or
  renamed.
- Chianca Di Ostuni, Milan Stone, Pulpis Brown, Terrazzo White, Total Grey, Total
  White: their live product pages carry only the single product-master image --
  re-checked directly against the current page, not just the OneDrive folder. No
  closeup/room photography exists on the site for these 6.
- Vein Tech trio: price book confirms these are the 20mm/bookmatched SKU of their
  base colour (same MB-code), not a separate product -- reused the base colour's
  productUrl and OneDrive photos; `slabSizes` set to the 20mm price-book size only
  (their 6/12mm sizes belong to the base-colour rows).

## Re-run
```
python tools/harvest_clay_galleries.py            # re-classify OneDrive folders (no network unless a folder is new/empty)
python tools/reconcile_clay_galleries.py --report  # dry run, prints the match table
python tools/reconcile_clay_galleries.py --apply   # writes images/ + slabs.json
```

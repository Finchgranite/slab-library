# KSG harvest report

Source: https://ksguk.co.uk/NATUREQ (old ASP-style CMS, curl-friendly). Quartz
range is branded "NATUREQ" on-site. Colour list cross-checked against the
NATUREQ index page and the 31 engineered (naturalStone: false) KSG price-book
colours; the 71 natural-stone KSG entries were never touched.

Each product page's "Product Information" block gives `Size:`/`Origin:`
directly. The main slab photo is the page's one visible gallery `<img>`;
close-up crops come from the page's own schema.org JSON-LD `Product.image`
field (which is frequently a DIFFERENT, closer-cropped photo than the gallery
hero) -- for White Shimmer and Carrara Gold the gallery has NO photo at all
("Image Coming Soon" / a mislabelled close-up-only hero) so the JSON-LD /
close-up-named photo was used as the main image instead, with status set to
`closeup-only` rather than `slab`.

## Counts
- Engineered KSG price-book colours: 31 (natural-stone KSG entries out of scope, untouched)
- Site pages fetched ok: 31
- No page on site (404): 1 -- Calacatta Gold Shimmer
- Mains newly set to "slab" (was missing): 11
- Mains upgraded to "slab" (was closeup-only/other): 0
- Mains set to "closeup-only" (only a close-up crop exists, no full slab photo): 1
- Main downloads that failed: 0
- Closeup gallery images added: 17
- Room gallery images added: 0 (site has none anywhere, confirmed in discovery)
- Metadata-only updates (productUrl/slabSizes/details/aliases): 30
- Colours with `image.status == "missing"` after this run: 0

## Price-book colours NOT found on the site
- Calacatta Gold Shimmer -- confirmed 404, no dedicated page exists even though
  the price book lists it distinctly from "Calacatta Shimmer". It already had
  an image on file from an earlier/other source (`image.status: "slab"`,
  unrelated to this harvest) so it is NOT `missing`, but `productUrl` could not
  be filled in and its image was never verified against ksguk.co.uk. Ask KSG
  whether it's still a distinct product or has been folded into "Calacatta
  Shimmer".

## Site colours seen but NOT in the price book (not harvested, not invented)
- Calacatta Frost (`/NATUREQ/quartz-calacatta-frost`)
- Dove (2652) (`/NATUREQ/quartz-dove-2652`)
- Pluto (2600) (`/NATUREQ/quartz-pluto-2600`)

## Assumptions / judgement calls
- **Carrara Gold**: the page's own gallery hero image is itself filename
  "Carrara Gold close up.jpg" (1280x853, 1.5:1) -- not a full slab shot despite
  being the only visible gallery photo. Treated as `closeup-only`, not `slab`.
- **White Shimmer**: gallery shows "Image Coming Soon"; the page's JSON-LD
  `Product.image` still resolves to a working close-up photo. Used as the
  main image with status `closeup-only` (matches the discovery note).
- Calacatta Shimmer's site photo filename is 'Calacatta Gold Shimmer_r_...' -- appears to be a leftover/reused filename on KSG's own Calacatta Shimmer page; used as-is since it IS what that page serves.
- `slabSizes` comes from the price book first; the page's own `Size:` line
  (metres, converted to mm) only as a fallback when the price book has no
  size row for that colour.
- `details` = "NATUREQ · <Origin> · <Finish> finish" from the page's own
  Product Information block + price-book Finish column.
- Existing `image.status == "slab"` mains are left untouched even where the
  site now has a close-up too -- the close-up is still added to `images[]`.
- Seville / Santorini: on-site names "Calacatta Light (Seville)" / "Calacatta
  Nero (Santorini)" recorded in `aliases[]`.
- Aspect-ratio warnings (auto-flagged, then eyeballed on the contact sheet --
  all four visually confirmed as genuine slab photos, no fix needed):
  - White Mirror / Amazon: real rectangular photos at 1.50:1 (7785x5193 /
    7890x5263) -- full-bleed slab-surface photography (no stand visible),
    just a squarer crop than KSG's usual ~2:1 on-stand shots. Kept as `slab`.
  - Andes / Desert Silver: the source files are literally SQUARE canvases
    (2731x2731 / 761x761, transparent PNG) with the slab photographed on a
    stand letterboxed inside (visible as a black band top/bottom on Andes'
    dark background; blends into white on Desert Silver's pale background).
    Confirmed by eye on the contact sheet -- genuine slab photos, not swatches
    or logos, just uncropped canvases. Kept as `slab`, not cropped.
- Pre-existing (not touched this run, flagging for the orchestrator): Santorini's
  current main (`ksg--santorini.webp`, status already "slab" before this run)
  is a moody black-background macro vein shot, a different photographic style
  from every other KSG main -- worth a second look, but per the "existing slab
  main left untouched" rule it was not replaced.

## Re-run
```
python tools/harvest_ksg.py                 # re-scrape (cached; delete tools/_cache/ksg to force)
python tools/reconcile_ksg.py --report       # dry run, prints the match table
python tools/reconcile_ksg.py --apply        # writes images/ + slabs.json
```

# RT Stone harvest report

Source: `https://www.quartzbyrtstone.co.uk/products` -- a single static listing page
(no sitemap.xml/robots.txt/wp-sitemap.xml -- all 404 on this custom LiteSpeed PHP
site) linking 111 per-colour pages at `product-details.php?title=<slug>`.
Despite all 38 pre-existing library entries storing `productUrl` as the generic
`/products` listing, real per-colour pages DO exist -- this run replaces the
generic URL with the real product page for every one of the 43 matched colours.

Each product page's own gallery is the `<img class="xzoom-gallery5">` set inside
`#magnific` -- NOT the plain `<img>` tags further down the page, which are a
"Related Products" carousel embedding every other colour's thumbnail (a
false-positive trap for a generic image scraper). Kind classification:
filename keyword first ("close up"/"closeup"/"zoom" -> closeup; "kitchen"
(incl. the site's own "KITHCEN" typo)/"fitted"/"room"/"install" -> room),
first image defaults to slab only when it carries no closeup/room keyword
itself (this correctly caught White Shimmer Supreme, whose sole gallery
image is filenamed "...CloseUP.jpg" -- the site has no slab face for it at
all); a handful of unlabelled middle images in a 3-image gallery were filled
in by position (slab/closeup/room is the consistent order everywhere this
was checked).

## Counts
- Site product-details pages (all colours/materials): 111
- RT Stone (quartz) price-book colours: 44
- Matched to a site product page: 43/44
- No site page found: 1 -- ['Eternal Calacatta']
- Mains newly set to slab (was missing): 4
- Mains upgraded to slab (was closeup-only): 1
- Mains upgraded missing->closeup-only (site has no slab face): 1
- Main downloads that failed: 0
- Closeup gallery images added: 34
- Room gallery images added: 23
- Ambiguous extra images skipped (no filename keyword, no positional anchor): 6
  -- Amigo Gold (2, a same-named duplicate slab photo + 1 unlabelled), Crystal Blue
     (2, same pattern), Calacatta Ice White (1, "ice white.jfif"), Calacatta Neo
     (1, "NEO.jfif") -- all 4 colours already had a confirmed `slab` main from an
     earlier pass, so nothing is lost by skipping these; worth a manual look if
     completeness of their galleries matters later.
- Still `missing` after this run: ['Eternal Calacatta']
- Still `closeup-only` after this run: ['White Shimmer Supreme']
- Site product pages with no matching price-book colour (other RT Stone ranges --
  granite/marble/onyx, or quartz colours we don't currently stock): 61
  -- ['Alaska Cream', 'Alaska White', 'Alpinous Onyx Quartz', 'Amigo Concrete', 'Aspen White', 'Bianco Eclipse', 'Black Forest', 'Black Galaxy', 'Black Pearl', 'Blue Dunes', 'Blue Fantasy', 'Blue Flower', 'Bohemia', 'Calacatta', 'Calacatta Classic', 'Calacatta Classic', 'Calacatta Extra', 'Calacatta Gold', 'Calacatta Gold', 'Calacatta Noble', 'Carrara Milano', 'Cemento Dark', 'Cemento Light', 'Colonial Cream', 'Colonial Gold', 'Colonial White', 'Cosmic Black', 'Costal Grey', 'Essenza', 'Fior Di Bosco', 'Imperial Gold', 'Indian Aurora', 'Ivory Brown', 'Ivory Fantasy', 'Kuppam Green', 'Laurent', 'Marron Mocha', 'Mist Black', 'Montblanc', 'Moon White', 'Nero Absolute', 'Nero Absolute', 'Nero Marquina', 'Paradise Classico', 'Platino Black', 'Platino Grey', 'Red Multi Colour', 'River Gold', 'River White', 'River White', 'Saphire Brown', 'Steel Grey', 'Stellar Beige', 'Stellar Dark Grey', 'Stream White', 'Studio Cream', 'Surf Green', 'Taj Mahal', 'Tiny Grey', 'Titanium Black', 'Viscon White']

## Assumptions
- Price-book "Cararra Milano" (typo) == site "Carrara Milano" -- explicit override,
  not a fuzzy match (the site spelling is presumably the correct one; worth fixing
  the price-book spelling at source).
- "Eternal Calacatta": no slug anywhere on `/products` contains "eternal" in any
  form -- likely discontinued/renamed on the current site. Still `missing`;
  `productUrl` set to the generic listing page as the HARVEST-SPEC fallback;
  `slabSizes` still filled from the price book (authoritative regardless).
- Several price-book colours have 2 site pages (an older "-jumbo"/plain SKU and a
  newer "-zero-silica"/"-super-jumbo-zero-silica" one) -- the zero-silica/newer
  variant was preferred (matches the site's own trend: some colours, e.g. Sand
  Storm, now ONLY have the zero-silica page, the old one retired), except
  Calacatta Auric where the older "-jumbo" page has the fuller gallery
  (slab+closeup+kitchen vs the "-super-jumbo" page's slab+closeup only) --
  spot-checked both before choosing.
- `details` = the page's own `<div class="prod_desc">` paragraph (a per-product
  description distinct from a longer generic marketing block also present on
  the page) -- used verbatim, truncated to 300 chars.
- `slabSizes` taken from the price book (authoritative, all 44 RT Stone colours
  have 20mm+30mm rows), not parsed from the page text.

## Lesson (bugs caught and fixed mid-run, before the successful `--apply` above)
Every gallery `href` on this site is DOCUMENT-relative (`images/Foo.jpg`, no
leading `/`) -- `hl._absolutize()` only resolves root-relative (`/x`) and
protocol-relative (`//host/x`) forms, so these needed an explicit
`urllib.parse.urljoin(page_url, href)` in `harvest_rtstone.py`. Separately,
the site's own raw filenames contain literal spaces/parens ("Alaska FULL
SLAB.jpg", "CARRARA BIANCO (1).jpg") that curl refuses outright (rc=3, "URL
using bad/illegal format") unless percent-encoded -- fixed by
`urllib.parse.quote(url, safe="/:%")`, applied strictly AFTER filename-keyword
classification (encoding first turned "close up"/"KITCHEN" into "close%20up"
and broke the classifier regexes -- caught by comparing the ambiguous-image
count between report runs, 6 vs 18). A first `--apply` attempt run before
these fixes landed downloaded 0 images (100% `DOWNLOAD FAILED`, curl rc=3/6
retried to exhaustion on every URL) and was killed by the orchestrator.

## Re-run
```
python tools/harvest_rtstone.py            # re-scrape (cached; delete tools/_cache/rtstone to force)
python tools/reconcile_rtstone.py --report  # dry run, prints the match table
python tools/reconcile_rtstone.py --apply   # writes images/ + slabs.json
```

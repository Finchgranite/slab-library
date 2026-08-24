# Thomas Group (Surfaces Collection) -- Quartz + Sintered Stone harvest report

Scope: 65 Quartz + 16 Sintered Stone price-book colours under supplier
"Thomas Group (Surfaces Collection)" (Porcelain/Atlas Plan is a separate agent's job).

Sources:
- Silkstone Quartz (27 colours, Thomas Group's own label) --
  thesurfacecollection.co.uk/products/silkstone-quartz/ (single page, all SKUs
  incl. End of Line). `lib/photos/*.jpg` = slab, `lib/swatch/*.jpg` = closeup.
- Vadara Quartz (37 colours) -- primary vadara.uk /designs/{slug}/ pages (34 of
  37; slugs from /product-sitemap.xml, not the small homepage carousel).
  `Vadara_{Name}_(Web|HiRes).jpg` = slab (HiRes preferred), `VQ_INSTALL_*`/
  `*_RenderNN.jpg` = room. `*_STORY_*.jpg` excluded (unrelated landscape mood
  photography, not product shots). No dedicated closeup exists on any page.
  3 "Super Jumbo" SKUs (Braewind, Nomad Valley, Soraline) have no vadara.uk page
  at all -- sourced from thesurfacecollection.co.uk's Vadara sub-pages instead
  (same lightbox pattern as Silkstone).
- Neolith by The Size (16 colours, Sintered Stone) --
  thesurfacecollection.co.uk/products/neolith-by-the-size/ (single page, all
  16). neolith.com is bot-blocked (HTTP 403 to curl) -- not attempted, per spec.

## Neolith reconciliation (Decisions: entry identity = one physical product)
5 of the 16 already exist in the library under plain supplier "Neolith"
(harvested from neolith.com directly) -- confirmed by matching the SKU code
embedded in each existing entry's neolith.com productUrl against the Thomas
Group colour's own SKU suffix:
| Thomas Group colour | -> existing Neolith entry | SKU evidence |
|---|---|---|
| Beton | Beton | exact name |
| Calacatta 01 | Calacatta (BM) | .../calacatta-**c01**-c01r/ |
| Calacatta Gold Cg01 | Calacatta Gold (BM) | .../calacatta-gold-**cg01**-cg01r/ |
| Estatuario 01 | Estatuario (BM) | .../estatuario-**e01**-e01r/ |
| Zaha | Zaha Stone | .../zaha-stone/ |

These 5 got "Thomas Group (Surfaces Collection)" added to `suppliers[]` and the
Thomas Group spelling added to `aliases[]` -- NOT duplicated. Note "Estatuario
E04" is a genuinely different Neolith SKU (E04, not E01) and got its own new
entry, not linked to "Estatuario (BM)".

The other 11 (Avorio, Basalt Beige, Bianco Carrara Bc02, Cement, Estatuario E04,
Iron Moss, La Boheme, Nero Marquina, Nieve, Phedra, Pierre Bleue) have no
equivalent existing entry (checked all 16 against all 45 existing Neolith
colours/productUrl SKU codes) -- new entries under supplier "Thomas Group
(Surfaces Collection)".

## Counts
- Silkstone: 27 price-book colours | created: 25 | not found: 2 (['Smokey Taupe', 'Venato Royale'])
- Vadara: 37 price-book colours | created: 37 | not found: 0
- Neolith: 16 price-book colours | created: 11 | linked to existing: 5 | not found: 0
- St Annes White (Architectural Material - Morris Homes, 1 colour) -- SKIPPED,
  not attempted. Bespoke housebuilder-contract SKU; not found anywhere on
  thesurfacecollection.co.uk, vadara.uk, or a plain web search (closest hit:
  Radianz "St Helens White", a different name/product). Recommend asking
  Thomas Group directly.
- Closeup gallery images added: 42
- Room gallery images added: 53
- No-photo-on-site colours (placeholder `pitem-na.jpg` on Silkstone page):
  ['Desert Silver (Silestone)', 'Honed Angelo White']

## Assumptions
- `slabSizes` comes from the price book (`hl.load_pricebook`) first; scraped
  page text only as a fallback when the price book has no size for that colour.
- Silkstone/Neolith TSC matching: normalise both sides (strip thickness "NNmm",
  finish words satin/silk/polished/leathered, dimension pairs "NNNN X NNNN"),
  then exact-match. "(End of Line)"/"Neolith " prefixes stripped from the
  price-book side only (site doesn't show them).
- Vadara own-asset filtering uses each design page's own `<h1 class="...
  post_title...">` text (not the price-book name) to pick which images belong
  to it -- the price book's spelling drifts from the site's in a few cases
  (Calacatta Dorad**o** vs site's Dorad**a**; Petr**o** Grigio vs site's
  Petr**a** Grigio) and the on-page title is authoritative for its own assets.
- Two Silkstone colours ("Desert Silver (Silestone)", "Honed Angelo White")
  resolve to a genuine product card but the site itself serves a
  `pitem-na.jpg` placeholder instead of a photo -- entries created with
  productUrl/details/sizes filled in, image left `status: "missing"`.
- Two Silkstone colours confirmed NOT on the site at all (checked again this
  pass, same as the discovery report): Venato Royale, Smokey Taupe.

## Re-run
```
python tools/harvest_thomasgroup_quartz.py             # re-scrape (cached; delete tools/_cache/thomasgroup to force)
python tools/reconcile_thomasgroup_quartz.py --report   # dry run, prints the match table
python tools/reconcile_thomasgroup_quartz.py --apply    # writes images/ + slabs.json
```

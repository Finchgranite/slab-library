# Thomas Group (Surfaces Collection) — discovery report (2026-08-24)

157 engineered price-book colours (76 Porcelain, 65 Quartz, 16 Sintered Stone).
**Resolved with a product URL: 150 (73 Porcelain, 61 Quartz, 16 Sintered). Not found: 7.**
Full colour-by-colour map: `tools/_reports/thomasgroup-discovery.json`.

## Distributor site
Thomas Group trades as **The Surface Collection**, `thesurfacecollection.co.uk`
(Urmston, Manchester; family firm since 1946 — NOT `thomas-group.co.uk`, that
domain is unrelated). It's a custom PHP/CMS site (WP-hosted assets mixed with a
bespoke `/lib/photos/`, `/lib/swatch/` product catalogue and lightbox popups —
`curl` works fine, no bot protection). Its own catalogue is comprehensive enough
to be a usable **fallback source for every one of the 157 colours** — but for
Porcelain and Vadara Quartz the brand's own site has noticeably better
photography (professional room/project shots), so use TSC as the verifier /
last-resort, not the primary.

## Ranges → brands
| Price-book section | Brand | Own/rebrand | Primary harvest site |
|---|---|---|---|
| Atlas Plan - * (76 colours) | **Atlas Plan** (an Atlas Concorde brand) | Rebrand (Italian manufacturer) | atlasplan.com |
| Silkstone Quartz - * (49 colours incl. End of Line) | **Silkstone** | Thomas Group's **own label** — no other manufacturer site exists | thesurfacecollection.co.uk |
| Vadara Quartz - * (37 colours) | **Vadara Quartz** (US) | Rebrand; Thomas Group became Vadara's official UK distributor Jan 2025 | vadara.uk |
| Architectural Material - Morris Homes (1: St Annes White) | Unclear — possibly Radianz | Bespoke contract SKU | unresolved, see below |
| Neolith by The Size - * (16 colours) | **Neolith** | Rebrand (Spanish, TheSize) | thesurfacecollection.co.uk (neolith.com is bot-blocked, see below) |

## Fetch notes & image patterns
- **atlasplan.com** — clean flat URL per colour: `/en/large-format-porcelain-slabs/{slug}/`
  (curl OK, plain UA). CDN `storage.atlasplan.com/public/assets/large-slabs/{slug}/...webp`.
  Each product page carries multiple kinds: full slab photos, bookmatch
  closeup/texture shots, and named "project"/kitchen room photos (filenames
  tag the colour, e.g. `...calacatta-extra-marble-effect-porcelain-stoneware-kitchen-worktops...`).
  Slab sizes printed as `162x324` (12mm main format), also `159x324`/`160x320`
  variants and `120x240`/`120x278` for some 6mm lines. Resembles the Cloudinary-CDN
  pattern the spec calls out — closest existing script analogue: none exactly,
  write fresh (category pages give the full slug list, ~6 category pages cover
  all sections: marble-effect, stone-effect, concrete-and-resin-effect,
  metal-effect, solid-effect, wood-effect).
- **vadara.uk** — WordPress (`wp-content/uploads`, wp-json present). Product
  pages at `/designs/{slug}/`; 5 named collections at `/collections/{slug}/`
  matching the price-book sections exactly (Divine Natural Majesty, Ebbs and
  Flows, Hidden Inspiration, Infusions, Threads of Nature). Main slab image
  `Vadara_{Colour}_Web.jpg`; many `VQ_INSTALL_{COLOUR}_H##.jpg` room/install
  shots per design (10–15 on some pages) — no dedicated closeup crop seen, the
  main Web.jpg doubles as slab+texture. Curl OK, no bot protection. **Matches
  `compac_harvest.py`'s WordPress/wp-content pattern almost exactly** — good
  template to copy.
- **thesurfacecollection.co.uk** — the single `/products/silkstone-quartz/`
  page (and similarly the Vadara/Atlas Plan/Neolith landing pages) embeds
  **every** SKU including ones not in the page nav (End of Line, Marble
  Collection) — don't rely on the sub-collection URLs alone, always also
  fetch the top-level page. Product headings carry finish + thickness +
  (for Neolith) full slab dims as plain text, e.g.
  `"CEMENT 3200 X 1600 X 12MM SATIN"`. Images at `/lib/photos/{Name}.jpg` and
  `/lib/swatch/{Code}.jpg`, referenced via a `data-bpopup` lightbox attribute
  (a "Slab Pictures & Sizes" link) rather than a plain `<img>` — a scraper
  needs to parse that attribute's embedded HTML, not just `<img src>`. Curl OK.
  No independent script precedent in `tools/`; closest is a generic HTML
  regex-scrape like `scrape_patterns.py`.
- **neolith.com — BLOCKED.** Returns HTTP 403 to curl even with a browser
  UA; it's Nuxt.js + Storyblok (`a.storyblok.com` CDN), effectively
  JS-rendered/bot-protected. This matches the existing library's "Neolith"
  supplier entries, which `tools/scrape_neolith_harvest.py`'s docstring says
  were **browser-harvested by driving Chrome page by page** — there is no
  curl-only path. Recommendation: use `thesurfacecollection.co.uk` as the
  primary source for these 16 Thomas Group Neolith colours (curl-friendly,
  covers all 16 with correct slab sizes) and only reach for
  claude-in-chrome on neolith.com if TSC's photo quality/resolution proves
  too low for the `slab`/`closeup`/`room` requirement.
- Sample-fetched ~24 pages total across the 4 sites this pass; all cached
  under `tools/_cache/thomasgroup/`.

## Reconciliation heads-up for the harvest agent
5 of the 16 Thomas Group Neolith colours plausibly already exist in the
library under the plain **"Neolith"** supplier (sourced from neolith.com
directly, not Thomas Group) with slightly different names — check before
re-harvesting: `Beton` (exact), `Zaha Stone`≈`Neolith Zaha`,
`Calacatta (BM)`≈`Neolith Calacatta 01`, `Calacatta Gold (BM)`≈`Neolith
Calacatta Gold Cg01`, `Estatuario (BM)`≈`Neolith Estatuario 01`. Decide
whether Thomas Group gets its own supplier entries (per HARVEST-SPEC's
"library colour must equal the price-book Colour for that supplier" rule)
or whether these should stay pointed at the existing "Neolith" entries —
that's an orchestrator call, not made here.

## Not found (7) — what was tried
- **Porcelain:** `Carrara Pure`, `Grigio Intenso` — confirmed to exist as
  Atlas Plan finishes via a third-party distributor (Gramaco) but no working
  atlasplan.com slug found across the 6 category pages crawled; `Kone Grey`
  — sibling `Kone Mix`/`Kone Gypsum` resolved, `Kone Grey` referenced by
  Gramaco but slug unconfirmed. All 3 worth a direct web search per-colour
  or an atlasplan.com sitemap fetch.
- **Quartz:** `Venato Royale`, `Smokey Taupe`, `Sardinian White Series 2` —
  Silkstone colours not found on the current thesurfacecollection.co.uk
  catalogue at all (sibling colours in the same collections did resolve);
  likely quietly discontinued/renamed, same as the 13 "End of Line" colours
  (which DID resolve — TSC still lists them despite the name). `St Annes
  White` (Architectural Material - Morris Homes, 1 colour) — not found
  anywhere; closest hit is Radianz's differently-named "St Helens White".
  TSC does list a separate, unfetched `/products/radianz-quartz/` line.
  Likely a bespoke housebuilder-contract SKU; low priority (1 colour) —
  recommend asking Thomas Group directly rather than more searching.

## Recommended harvest plan
1. **Porcelain (73/76):** primary atlasplan.com, one script crawling the 6
   category pages for slugs then each product page for slab/closeup/room
   images + printed sizes. New script, ~half a day.
2. **Vadara Quartz (all 37 resolved):** primary vadara.uk, WordPress —
   copy/adapt `compac_harvest.py`'s wp-content pattern, walk the 5
   `/collections/{slug}/` pages for the product list then `/designs/{slug}/`
   for images.
3. **Silkstone Quartz (all 49 incl. discontinued resolved):** only source is
   thesurfacecollection.co.uk — new lightweight script parsing the
   `data-bpopup` lightbox HTML on the single `/products/silkstone-quartz/`
   page (don't bother with the sub-collection URLs, they're redundant/incomplete).
4. **Sintered Stone / Neolith (all 16 resolved):** thesurfacecollection.co.uk
   `/products/neolith-by-the-size/*` pages, same lightbox-parsing script as
   Silkstone; reconcile against the existing "Neolith" supplier entries first
   (see above) before adding new ones.
5. Chase the 7 "not found" by direct web search / a plain-text request to
   Thomas Group; low priority relative to the 150 already resolved.

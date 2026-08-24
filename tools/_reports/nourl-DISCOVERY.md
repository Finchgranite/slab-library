# No-URL suppliers — discovery report (2026-08-24)

Seven suppliers, 234 engineered price-book colours with no `productUrl` in `slabs.json`:
LuxeStone (22), KSG (31), Lumina Stone (18), Nile Stone (52), Unistone (33), Brachot (35),
BQS (43). Investigated as four research passes (grouped where suppliers looked related).
Full colour-by-colour map for all 234: `tools/_reports/nourl-discovery.json`.

**Resolved with a product URL: 203/234. Not found: 31** (22 LuxeStone — no supplier site
exists at all; 2 Lumina Stone — Bronze Cascade, Urban Cemento; 1 KSG — Calacatta Gold
Shimmer). Zero unresolved for Nile Stone, Unistone, Brachot, BQS.

## Headline finding: three of the seven are one company

**Brachot, Unistone and BQS are all Brachot** (Belgian stone group, family firm since 1901,
Brachot-Hermant). One site, `www.brachot.com`, one Next.js/Storyblok stack, one URL family
`/en/materials/{code}/{slug}-{brand-suffix}/`:
- `-uniceramica` → **Brachot** (porcelain, 35/35 resolved) — "Uniceramica" is Brachot's own
  in-house porcelain brand, not an external Italian manufacturer despite the Italian finish
  names (Bocciardata/Lucidato/Naturale/Ondulato/Strutturata).
- `-unistone` / `-unistone-uniq` → **Unistone** (quartz, 33/33 resolved) — Brachot's own
  in-house quartz brand ("Unistone is a premium quartz surface collection developed by
  Brachot" — corroborated by multiple independent UK resellers).
- `-bqs` → **BQS** = "Brachot Quartz Surfaces" (quartz, 43/43 resolved) — a third,
  separate Brachot quartz line, own brochure ("brochure-bqs-slabs_uk_...pdf"), own
  "Mirrorlux"/"Velluto" finish names. Colour overlap between Unistone and BQS is minimal
  (only "Taj Mahal" shared by name) — these are two distinct in-house quartz ranges, not
  one range under two labels.
- One company, one site — but **porcelain vs quartz vs the two quartz sub-brands are
  chemically/manufacturing-wise distinct products with distinct photography**. Do NOT share
  images across a same-named pair (e.g. Brachot "Statuario" ≠ Unistone "Statuario"; BQS
  "Super White Plus" ≠ Unistone). Harvest each from its own product URL.
- No "Diresco" connection found anywhere on brachot.com or in search — that hypothesis
  didn't pan out.
- Full colour list for all three obtained from `brachot.com/sitemaps/sitemap-en.xml`
  (the `/en/materials/` filter page is JS-populated and has no static product list) —
  filter for `-uniceramica` / `-unistone` / `-bqs` suffixes.
- Product-page data lives in a `__NEXT_DATA__` JSON blob (BQS/Unistone) or is reachable via
  the same pattern (Brachot) — `materialPim.images[]` (cdn.pimber.ly, full-res product
  photos), `materialStory.finishes[].image` (a.storyblok.com, ~1920x945px slab crops, one
  per finish sold), plus dedicated `/en/references/{id}/kitchen-...` room-photo pages
  (covering ~12 of BQS's 43, most of Brachot's 35). No bot protection, plain curl works.
  Image URLs are wrapped in a Next.js proxy (`/_next/image/?url=<encoded-cdn-url>`) — decode
  the `url=` param for the original, uncapped-resolution asset.
- Known data quirks to fix before harvest: `unistone--cararra-misterio` is a price-book
  spelling typo for Brachot's "Carrara Misterio" (needs an `aliases[]` entry — this is also
  Unistone's one missing-image colour); several Brachot/BQS colours have duplicate site
  codes for the same design (batch-variant `-a`/`-b` suffixes, or genuine dupes like
  `ksxcal`/`ksxmca` for Capraia) — use the base/unsuffixed code; BQS's "Avenza" =
  site's "Avenza Avorio BQS", "Neo Calacatta" = site's typo'd "Neo Calcatta BQS", same
  products under slightly different site labels.
- Nile Stone's "Travertino Classico" name-collides with Brachot's — confirmed via search to
  be a generic Italian trade term for a common travertine look, used industry-wide; the two
  are unrelated products from unrelated manufacturers (Nile's is natural stone anyway, out
  of scope). Do not merge.

## Nile Stone — 52/52 resolved

**Nile Trading UK Ltd**, trading as "Nilestone" (Hemel Hempstead). Two distinct lines:
- **Quartz (41, own label, "Nile Quartz Surfaces")** — `nilestone.co.uk` is an Angular SPA;
  curl on any page returns only an empty shell, BUT the entire catalogue (id/title/images[])
  is hardcoded as a JS object literal inside the compiled `client/main.*.js` bundle, fully
  scrapable via curl + regex without a headless browser. Static image assets
  (`nilestone.co.uk/assets/quartz-surfaces/{filename}`) fetch fine directly, no bot
  protection on the CDN even though the HTML is JS-only.
- **Porcelain (11) — Marazzi "The Top", CONFIRMED rebrand.** Nile Trading is Marazzi's sole
  UK distributor for The Top (trade press + multiple reseller pages corroborate). Primary
  harvest source is Marazzi's own UK site, **`marazzitile.co.uk`** — ordinary
  server-rendered WordPress-family site, curl-friendly, no bot protection, and noticeably
  better photography (printed size/product code + a genuine room/project-photo gallery
  captioned by colour) than nilestone.co.uk's own generic single-image `/top-marazzi` page
  (use the latter only as fallback/verifier). No per-colour URL exists on either site — all
  colours sit on shared collection pages (6 `/collections/grande-{look}-collections/` pages
  on marazzitile.co.uk; single `/quartz-surfaces` and `/top-marazzi` pages on nilestone.co.uk).
- Caveats: Black and Limestone Sand porcelain only found via Nile's lower-quality image, not
  on marazzitile.co.uk's collection pages (worth a second pass/site search); the White SKU
  found on marazzitile.co.uk is Lux finish vs the Matt/Natural finish actually stocked
  (different SKU code, note before harvest); Silver Root Grey/White are confirmed genuinely
  distinct products, not a naming duplicate.
- No fresh-script precedent matches exactly — recommend two small new scripts (regex-over-JS
  for Nile Quartz; HTML `<p>`/`<img>` pair-parsing for Marazzi Grande, no lightbox attribute
  to unpack, simpler than Thomas Group's TSC pattern).

## KSG — 30/31 resolved

**ksguk.co.uk**, KSG(UK) LTD (Companies House 08378438, Annesley, Notts) — old-school
ASP-style CMS, no bot protection, curl works cleanly on every page. Quartz range is branded
**"NATUREQ"** on-site (price book's "KSG Quartz" is Finch's internal label). URL pattern
`ksguk.co.uk/NATUREQ/quartz-{slug}` (one quirk: Avalanche is `/NATUREQ/QuartzAvalanche`, no
hyphen). Seville and Santorini are aliased on-site as "Calacatta Light (Seville)"/"Calacatta
Nero (Santorini)" — capture both forms in `aliases[]`. Pages state `Size: 3.20 x 1.60`,
`Origin: KSG Factory India` directly. **No room/kitchen photos anywhere on the site** — the
Gallery page is placeholder content; expect `slab` (+ sometimes `closeup`) only, `room` will
be `missing` for every KSG entry. All 12 previously-missing colours resolve to a real photo.
White Shimmer is a genuine partial gap: its visible gallery shows "Image Coming Soon" but the
page's own schema.org JSON-LD still points at a working closeup image — a harvest script must
read the JSON-LD `image` field, not just scrape `<img>` tags. Not found: **Calacatta Gold
Shimmer** — 404s to the category listing, no dedicated page exists on KSG's own site even
though the price book lists it as a distinct colour from "Calacatta Shimmer"; recommend
asking KSG directly rather than more searching.

**KSG vs Kingstone verdict: different, unrelated companies** (Kingstone is a separate
existing price-book supplier, 70 rows, own "Kingstone Quartz" section). Different registered
entity/address/phone, different tech stack (KSG = ASP per-colour pages; Kingstone = WordPress,
all colours on one listing page, no per-colour URLs), different catalogue style (KSG =
geography names; Kingstone = numbered SKUs like "Taj Mahal 230"), no "also known as" language
anywhere. Only ~7 of 66 combined names overlap — consistent with two importers both stocking
some industry-generic quartz designs, not a shared identity. **Source KSG's colours from
ksguk.co.uk, never kingstonequartz.co.uk.**

## LuxeStone — 0/22 resolved: no public website exists

Exhaustive domain guessing (7 plausible `.co.uk`/`.com` variants, all DNS failures) and web
search (brand name, "LuxeStone quartz UK", per-colour searches) found **no UK quartz-worktop
trading identity called LuxeStone**. The only live near-match, `luxe-stone.co.uk`, is an
unrelated tile retailer ("LUXESTONE TILES LIMITED", Hayes, inc. June 2025). The price book's
own source citation is the tell: every LuxeStone row cites **"LuxeStone Quartz Price List V1
Jan 2026"** — a dated PDF, not a URL — plus trade-account pricing language (Group 1-4 tiers,
"JU"/"SJ" Jumbo/Super Jumbo). **Conclusion: LuxeStone is a trade-only wholesaler that sells
via a distributed PDF price list with no public storefront — HARVEST-SPEC's "from the
supplier's own website" requirement cannot be met as things stand.** One relevant negative
data point: LuxeStone's "Superior Calacatta" is sold under the identical name by a *different*
UK reseller (work-tops.com) attributed to a *different* brand ("Fugenstone", same 3200x1600mm
format) — proof this is an industry-wide generic OEM design name licensed by multiple UK
sellers, not evidence of a shared identity with any of Finch's other suppliers. Recommend the
orchestrator ask Graham for LuxeStone's PDF price list / photo pack directly, or leave all 22
colours `missing` and flag for him.

## Lumina Stone — 16/18 resolved

No single authoritative UK site: global brand sites are `luminastone.eu` (WordPress) and
`luminastone.com.au`; `luminastone.co.uk` 404s. **Imported into the UK exclusively by Granite
Granite Ltd of Basildon**, whose own domains didn't yield a usable catalogue this pass
(wrong-site DNS anomaly / connection refused). Best practical source: **`pisastone.co.uk/
quartz-worktops/lumina-stone`**, a single reseller catalogue page with all 16 currently-UK-
stocked colours, 4-digit SKU codes, one slab photo each (no per-colour URLs — `productUrl`
for every Lumina entry would point at this shared page). Resolved Patagonia's slab-shot gap
(previously closeup-only). `luminastone.eu`'s own current catalogue has moved on to a
refreshed colour range (only 7 of our 18 names cross-confirm there, useful for a couple of
supplementary room/portfolio photos on Sand Swan and White Swan). **"S-Tech"/"Silica-Free"**
appear to be Lumina's own proprietary finish-tech naming, not a rebrand signal. Not found:
**Bronze Cascade, Urban Cemento** — both share the (rare) Silica-Free finish flag, a
suspicious pattern suggesting a newer/thinner-coverage sub-line; a fourth reseller
(granitewarehouseyork.co.uk) has a dedicated Lumina page but connection-failed this pass
(worth a claude-in-chrome retry) — otherwise recommend asking Granite Granite Ltd directly.

## BQS — 43/43 resolved

Covered above under the Brachot/Unistone/BQS relationship — see that section for site,
image, and reconciliation details.

## Recommended harvest order (by ease and coverage)

1. **Brachot / Unistone / BQS (111 colours, 111 resolved)** — one script against
   brachot.com's sitemap + `__NEXT_DATA__`/Next-image-proxy pattern covers all three.
2. **Nile Stone (52 resolved)** — two small scripts (JS-bundle regex for Nile Quartz;
   HTML pair-parse for Marazzi Grande porcelain).
3. **KSG (30 resolved, 1 flagged)** — straightforward per-colour ASP pages, watch for the
   JSON-LD-only White Shimmer image.
4. **Lumina Stone (16 resolved, 2 flagged)** — single reseller catalogue page scrape.
5. **LuxeStone (0 resolved)** — blocked; needs Graham's direct input (PDF/photos) before any
   harvest is possible.

## Cache / scratch

Cached pages under `tools/_cache/{brachot,unistone,nile-stone,marazzitile,ksg,kingstone,
luxestone,lumina-stone,bqs}/`. No changes made to `slabs.json`, `images/`, or git.

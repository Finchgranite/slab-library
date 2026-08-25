# Slab Library harvest spec — phase 2 (2026-08-24) — READ FULLY BEFORE ANY WORK

Owner: Graham Finch (Finch's Stone & Marble). Orchestrated by Claude (Fable). Harvest agents
run on Sonnet, one supplier each. This file is the contract every agent follows.

## Goal
For every ENGINEERED colour we sell (Quartz / Porcelain / Sintered Stone / Ceramic — NOT
granite, marble, quartzite, onyx, travertine, slate, or anything `naturalStone: true`), the
library holds, from the supplier's own website:
1. **slab** — the official full-slab image (main; `image` field). Slab-face only, ~2:1 aspect.
2. **closeup** — a texture/detail crop, if the site has one.
3. **room** — a kitchen/bathroom/installation photo, if the site has one.
Plus `productUrl`, and where the page states them, `slabSizes` (e.g. "3200x1600 20/30mm") and
`details` (finishes, ranges, short supplier blurb — one line).
**Natural stone is OUT OF SCOPE for this phase** — Graham's rule: slab photos of natural
material mean nothing once that block is gone; a general description serves better. Leave
natural entries untouched.

## Where things live
**Two PCs.** Home PC (user `thefi`): repos directly under `C:\Users\thefi\`. Works PC (user
`graha`): repos under `C:\Users\graha\projects\` and OneDrive under `C:\Users\graha\OneDrive - …`.
**Never hardcode either — `harvest_lib` resolves `LIB_ROOT`, `SLABS_JSON`, `IMAGES_DIR`,
`PRICEBOOK_CSV`, `BRANDS_ROOT` for whichever PC you are on (added 2026-08-25); import it and
use those constants.** The `thefi` paths below are the home-PC spellings.
- Library repo: `C:\Users\thefi\slab-library` (PUBLIC GitHub — NEVER put prices in it).
  `slabs.json` (top-level `generated` + `slabs[]`), `images/` (webp, max 1600px wide,
  `{supplier-slug}--{colour-slug}.webp`; galleries `{id}--closeup1.webp`, `{id}--room1.webp`…).
- Originals (full-res downloads) go to OneDrive:
  `C:\Users\thefi\OneDrive - Finch's Stone & marble Ltd\Brands -Slabs -Kitchens-Website\`
  `1. QUARTZ\<SUPPLIER FOLDER>\<Colour>\` (porcelain/sintered: `3. PORCELAIN & SINTERED\…` —
  create if absent; use the price-book colour name for the folder).
- Price book (private, read-only for you): `C:\Users\thefi\stone-worktop-quotes\materials\
  supplier-price-book.csv` — columns Material, Colour, Thickness (mm), Finish, Supplier…
  It is the naming authority: library `colour` must equal the price-book `Colour` for that
  supplier. `tools/_pb_missing.json` lists price-book colours with no library entry.
- Proven scripts to copy the pattern from: `tools/compac_harvest.py` + `compac_reconcile.py`
  (WordPress/wp-content), `clay_harvest.py`/`clay_reconcile.py` (token-subset name matcher),
  `akg_wp_sweep.py` (LESSON: harvest BOTH the CDN pattern AND plain <img>/wp-content sources),
  `bloom_harvest.py` (Wix 429s python urllib — FETCH WITH CURL), `slabify_supplier.py`
  (true-scale pass, optional here). Shared helpers, once they exist: `tools/harvest_lib.py`.

## Schema additions (this phase)
- `images[]` items gain `"kind": "slab" | "closeup" | "room"`. The main `image` is always the
  best slab. Existing `images[]` items without `kind` are slab.
- `image.status` stays: `slab` | `closeup-only` | `representative` | `missing`.
- New optional `aliases: []` on an entry (other names the supplier/price book uses).
- **Any script that changes images or data MUST bump top-level `generated`** (ISO timestamp)
  or Pages/browser caches serve stale images.

## Rules of the road
1. Fetch with `curl -sL -A "Mozilla/5.0 …" --max-time 90` via subprocess; cache pages to
   `tools/_cache/<supplier>/`; 2s between requests; back off on 429/5xx. Never hammer a site.
2. Image kind classification: filename/alt/section hints first (slab/plaka/tablero/full,
   detail/closeup/texture/zoom, kitchen/room/ambient/inspiration/application/project);
   then aspect (≈1.8–2.3:1 = slab candidate; ~1:1 tile = closeup; wide photo with cabinets =
   room). If unsure, save it under `_unsorted/` in the OneDrive colour folder and say so.
3. Prefer the original over -WxH scaled variants. Skip logos, icons, swatches < 300px, PDFs.
4. Name matching to the library/price book: normalise (lowercase, strip non-alnum), then
   token-subset with the known quirks (range prefixes, "Extra Statuario"/"Statuario Extra",
   Gray/Grey, Aegan/Aegean, ™/®, colour-code suffixes). Report every unmatched site product
   AND every unmatched price-book colour — don't invent entries for products we don't sell
   unless the price book has them; DO add entries for price-book colours the site confirms.
5. Produce a **contact sheet** PNG of all mains (`tools/_reports/<supplier>-mains.png`, ≤8 per
   row, labelled) and one of galleries. Never call a supplier done without it.
6. Write `tools/_reports/<supplier>-REPORT.md`: counts (site products / matched / added /
   mains replaced / closeups / rooms / unmatched both ways), assumptions, anything to ask the
   supplier, and the exact commands to re-run. Keep it under a page.
7. Apply to `slabs.json` + `images/` yourself (idempotent scripts, `--report` then `--apply`),
   bump `generated`. **Do NOT git commit or push** — the orchestrator reviews the contact
   sheet and commits per supplier.
8. Don't touch other suppliers' entries. Don't delete images. Don't edit review.html unless
   told (the orchestrator owns UI changes).
9. Your final message must be a short data summary (counts + report path + rough token use
   if you can tell), not prose for a human.

## Decisions (orchestrator, 2026-08-24 evening)
- **Entry identity = one physical product.** If a distributor (e.g. Thomas Group) sells a brand
  that already has library entries (e.g. Neolith from neolith.com), do NOT create a duplicate:
  add the distributor's price-book supplier name to that entry's `suppliers[]` and the
  distributor's spelling to `aliases[]` (e.g. "Calacatta (BM)" → Neolith "Calacatta 01").
  The price-book join then resolves via supplier ∈ {supplier} ∪ suppliers[] and colour ∈
  {colour} ∪ aliases[]. Only create a new entry when the product truly isn't there.
- **New brands sold via a distributor** (Atlas Plan, Vadara, Silkstone via Thomas Group):
  `supplier` = the price-book supplier string exactly ("Thomas Group (Surfaces Collection)"),
  `details` starts with the brand + range ("Atlas Plan · Marble Look · 12mm hammered/natural…"),
  `productUrl` = the brand's own page when one exists, else the distributor page. Images from
  the brand site first (better photography), distributor site as fallback/verifier.
- **Bot-blocked sites** (neolith.com): do not fight it; use the distributor's pages, note it
  in the report, and list the colours whose photos are low-res so a browser pass can be done
  later by the orchestrator.
- **Thomas Group harvest plan** (from tools/_reports/thomasgroup-DISCOVERY.md): Atlas Plan via
  atlasplan.com category pages → per-colour pages (storage.atlasplan.com CDN, slab + bookmatch
  closeup + project/kitchen room shots, sizes 162x324 etc.); Vadara via vadara.uk (WordPress —
  copy compac_harvest.py; `Vadara_{Colour}_Web.jpg` = slab, `VQ_INSTALL_*` = room); Silkstone
  + Neolith via thesurfacecollection.co.uk (parse the `data-bpopup` lightbox HTML, not just
  <img>; `/lib/photos/{Name}.jpg`; headings carry finish/thickness/dims). Always fetch the
  top-level product page too — End of Line SKUs only appear there.

## Concurrency rule (added after the Caesarstone pilot, 2026-08-24 ~20:30)
Several supplier agents run AT THE SAME TIME. `slabs.json` is shared. Therefore:
- **Apply through `harvest_lib.patch_library(mutate, supplier="<your supplier>")`** — it takes
  the lock, re-loads the file fresh, runs your mutate(lib), saves atomically with the
  `generated` bump, and REFUSES to save if you touched another supplier's entries. Never
  `load_library()` → edit → `save_library()` across a long download loop: do all downloads
  and webp conversion first, then one short patch_library() call to write the entries.
- Image files are per-entry-named so they never collide; page caches are per-supplier.
- The Caesarstone pilot (`tools/harvest_caesarstone.py` + `reconcile_caesarstone.py`) is the
  worked example: sitemap → per-page harvest JSON → `--report` → `--apply`.

## Budget rule (added 2026-08-24 ~21:00 after the no-URL discovery spent ~575k tokens)
- **Do NOT spawn sub-agents.** One agent = one supplier = one context. Sub-agents tripled the
  cost of a discovery pass with no better result. If the job is too big for one context,
  finish what you can, write the report, and say what's left.
- Fetch only what you need: one listing/sitemap pass, then one page per colour. Do not
  re-fetch cached pages; do not view contact-sheet images at full size more than once.

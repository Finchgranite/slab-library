# Slab Library — Finch's Stone & Marble

A visual database of every slab colour in the supplier price book: one entry per
supplier + colour, with a product page link and a **full-slab image**.

**No pricing lives in this repo** (it is public so GitHub Pages can serve the
images). Prices are joined in locally from `stone-worktop-quotes/materials/
supplier-price-book.csv` by matching `supplier` + `colour`.

## Files

- `slabs.json` — the database. One entry per supplier+colour product.
- `images/` — one WebP per colour, max 1600px wide, named `{supplier-slug}--{colour-slug}.webp`
- `review.html` — visual review page (GitHub Pages) for checking image matches
- `tools/build_library.py` — scans the OneDrive brand folders, matches colours
  to the price book, picks the best slab image, converts to WebP

## Image status flags (`image.status`)

| status | meaning |
|---|---|
| `slab` | proper full-slab shot |
| `closeup-only` | only a close-up/sample shot found — needs review, may borrow |
| `representative` | borrowed from a near-identical colour (`image.borrowedFrom` says which) |
| `missing` | no image yet |

## Rules

- **Natural stone** (granite, marble, limestone, quartzite…): ONE image per
  colour name shared across suppliers, and `illustrationOnly: true` — every
  display must carry the warning *"Illustration only — natural stone varies;
  this is not the actual slab your worktop will be cut from."*
- Near-identical quartz colours may share a representative image
  (e.g. B-Stone Brilliant Ice ≈ Picasso Snowdale ≈ IQ White Galaxy).
- Slab images only — no kitchen shots, no close-ups as the primary image.

## Workflow

Images come from the OneDrive folder
`Brands -Slabs -Kitchens-Website` (1. QUARTZ / 2. GRANITE & NATURAL STONE /
3. CERAMIC- PORCELAIN) first; supplier-website scraping is the fallback.
Run `tools/build_library.py` per supplier, review via `review.html`, commit.

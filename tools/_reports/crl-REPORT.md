# CRL harvest report

Source: `https://crlstone.co.uk/wp-json/wp/v2/collection` (WP REST API, `_fields=slug,link,
title,content,excerpt` -- the listing call itself returns each colour's full rendered page
HTML, so 2 paginated requests covered all 102 currently-live colour pages; no per-colour
fetch needed). 18 library colours (12 closeup-only + 6 missing) are NOT in that listing and
return "no results" on-site search -- delisted/discontinued by CRL. `archive.org`'s Wayback
Machine has a snapshot for 12 of those 18; their image files still resolve directly on the
LIVE crlstone.co.uk domain even though the product page itself is gone (verified: a
`Materia-Gris-Slab-image-*.jpg` URL returns HTTP 200 on crlstone.co.uk while
`/surfaces/matteria-gris/` 404s) -- fetched from there first, the archive.org image proxy as
fallback. 6 colours have no wayback snapshot either: Dual Blanco, Dual Negro, Larsen Super
Blanco Gris, Masai Blanco Plus, Masai Piedra, Matteria Taupe -- still `missing`/`closeup-only`.

Where a colour already had originals downloaded to OneDrive from an earlier pass
(`1. QUARTZ\CRL Quartz\<Colour>\`, mostly quartz colours -- the porcelain "Ceralsio" folder
was essentially empty), those local files were reused for the gallery instead of
re-downloading (classified by filename: `*Slab*`=slab, `*Zoom*`/`*Close-Up*`/`*close-detail*`
=closeup, `*kitchen*`/`*Header*`=room).

## Counts
- CRL library entries: 109 (51 quartz + 58 porcelain per the brief's 109 total)
- Matched to a live or wayback-recovered site record: 98
- Mains newly set (was missing): 5
- Mains upgraded (was closeup-only): 7
- Closeup gallery images added: 104
- Room gallery images added: 187
- productUrl placeholders (`?s=` search links) replaced with a real page/archive link: 18
- Still `?s=` placeholder after this run (no site/wayback match found): ['Ananda Blanco', 'Brazza Crema', 'Dual Blanco', 'Dual Negro', 'Larsen Super Blanco Gris', 'Masai Piedra', 'Matteria Taupe', 'Storm Gris', 'Storm Negro', 'Totem Gris']
- Still not status=slab after this run: ['Dual Blanco', 'Dual Negro', 'Larsen Super Blanco Gris', 'Masai Blanco Plus', 'Masai Piedra', 'Matteria Taupe']
- Library colours with no site or wayback match at all: ['Ananda Blanco', 'Brazza Crema', 'Dual Blanco', 'Dual Negro', 'Larsen Super Blanco Gris', 'Masai Blanco Plus', 'Masai Piedra', 'Matteria Taupe', 'Storm Gris', 'Storm Negro', 'Totem Gris']
- Live site colours with no library/price-book match (site sells, we don't currently stock,
  or price-book name differs) -- 16: ['Arctic White Polished', 'Bianco Silver', 'Cardoso Grey', 'Cosmopolitan Silver', 'Croma Black', 'Croma Grey', 'Croma White', 'Grassi White', 'Montblanc White', 'Moon Gris', 'Oxford Grey', 'Platinum', 'Soft Concrete', 'Stone', 'Syros Super Blanco Gris', 'Varese Onice']

## Assumptions / notes
- `slabSizes` taken from the price book (`hl.load_pricebook("CRL")`, which already has sizes
  for all 109 CRL colours) rather than parsed off the page -- price book is the sizing
  authority per HARVEST-SPEC.md.
- `details` = "CRL {Quartz|Ceralsio (Porcelain)} · {finishes from price book} · {blurb}",
  blurb = the page's first 1-3 marketing paragraphs (skipping the generic "part of our silica
  free collection" note), truncated to ~340 chars total.
- For the 5 colours Ananda Blanco / Brazza Crema / Storm Gris / Storm Negro / Totem Gris:
  already `slab` status from an earlier "web"-sourced pass (not crlstone.co.uk), not present
  in the current 102-page listing, and archive.org rate-limited (HTTP 429) this run before a
  wayback check could complete for them -- productUrl left as the `?s=` placeholder; worth a
  follow-up wayback check once archive.org's rate limit clears (Storm Gris already has 10
  originals in the OneDrive porcelain folder from a prior pass, reused for its gallery here).
- Site colours with no library/price-book claim (Soft Concrete, Croma White/Grey/Black,
  Grassi White, Montblanc White, Varese Onice, Bianco Silver, Cosmopolitan Silver, Cardoso
  Grey, Stone, Platinum, Pacific Blanco, Moon Gris, Syros Super Blanco Gris, Oxford Grey,
  Arctic White Polished, Labradorite Royal Blue) are CRL ranges we don't currently stock --
  not added, per the "don't invent entries" rule.
- Never replaced an existing `status: "slab"` main, per the DON'T REPLACE rule, even where the
  live page's own "Full Slab" widget is now empty (Polar White, Grey Reflection, Cristallo
  Perla, Clear White, Windsor Grey all have this) -- their productUrl/gallery were still
  filled from the live page.

## Re-run
```
python tools/harvest_crl.py            # re-scrape (cached; delete tools/_cache/crl to force)
python tools/reconcile_crl.py --report  # dry run, prints the match table
python tools/reconcile_crl.py --apply   # writes images/ + slabs.json
```

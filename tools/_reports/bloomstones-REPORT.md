# Bloomstones (Quartz + Porcelain) harvest — 2026-08-24

## Ground truth used
Not `<img>` scraping — the Wix "wix-warmup-data" CMS collection JSON embedded in
each product page (`QuartzSamples.mediaPics[]` / `PorcelaineSlabs.images[]`),
each item carrying a real `fileName`/`title`, media slug, and true
`originWidth`/`originHeight`. One quartz page embeds the **entire 51-item**
QuartzSamples collection; each porcelain page embeds only its own record but
that record's own gallery is complete. Discovery via the three Wix dynamic
sitemaps (`dynamic-quartz-samples...`, `dynamic-porcelaine-slabs...`) — 51
quartz + 29 porcelain product pages, 80 total.

## Counts
- Site engineered colours (quartz + porcelain): **80** (51 quartz, 29 porcelain)
- Matched to library entries: **80 / 80** (custom token-subset matcher, DROP-list
  tuned for this site's finish-suffix titles, e.g. "Calacatta Gold Polished and Matt")
- New entries created: **0** (every site colour was already a library entry)
- Mains added / replaced: **0** — see "34 missing" below
- Closeup images added: **52**, across **28** entries (cap 4/entry)
- Room images added: **1** (see note below)
- Unmatched site colours: **0**
- Library engineered colours the site does **not** confirm (still `missing`): **34**

## The 34 still-missing mains (goal 1) — every one checked against the live site
`Arctic Wave, Aurora Beige, Base Ash, Bayside, Blue Sparkle, Calacatta Aurelia,
Calacatta Gold X, Calacatta Nile, Calacatta Panda, Calacatta Royale, Calacatta
Verde (porcelain), Calacatta Viola, Carrara Gold, Carrara Luni, Concreto Light,
Cristallo Extra, Cristallo Grigio, Empire Grey, Fusion White, Glacial Rift, Gold
Cream, Ice Jade, Klitkin, Lea White, Limestone Cream, Luxury White, Onice, Onix
Turqoise Plus, Sensa Taj Mahal, Snow X, Taj Velvet Cascade, Trani Beige, Venus
Gold, Vintage Stone Fog`

33 of these have **no page at all** on bloomstoneslondon.com today — not in the
sitemap, no CMS record. The site's live catalogue (80 colours) is materially
smaller than what's in the price book/library; these are presumably
discontinued-from-web or physical-only SKUs. One, **Aurora Beige**, does have a
live page and price-book match (`/quartz-samples/aurora-beige-`, confirmed via
CMS record) but that record's `mediaPics` field is empty — the supplier never
uploaded a photo for it. `productUrl`/`slabSizes` were still filled in for it
from the confirmed page + price book, image left `missing`.

Also confirmed dead: `/kitchen-samples/*` (the room-photo collection
`bloom_harvest.py` used previously) 404s site-wide and has no sitemap entry any
more — there is currently no room-photo source on this site at all.

## Notable finding: one image required reclassification, not the main slot
`Statuario Versilia`'s gallery included a birds-eye kitchen/living-room photo
that aspect-ratio-classified as "closeup" (near-square crop, no filename
hint). Caught in visual verification, reclassified `kind: room,
status: representative`, file renamed `--closeup1` → `--room1`. No other
gallery image failed visual spot-check (verified ~10 of 52 directly, plus the
full 8-per-row contact sheet).

## Assumptions / minor risk
- `Taj Mahal Polished and Matt` (site) was matched to the existing
  `bloomstones--natural-taj-mahal` entry (only porcelain "Taj Mahal"-named
  product on site) rather than the still-missing `Sensa Taj Mahal`. Main image
  untouched either way (already `status: slab`); only `productUrl`/gallery
  added — worth a human glance if Graham cares about the distinction.
- `details` synthesized as `"Bloomstones · <Material> · <finishes from price
  book>"` only where the field was previously empty; never overwrote existing
  values.
- Existing `status: slab` mains were never touched (file, source, or `scale`),
  per spec — including the ~13 previously `approx`-scale ones.

## Re-run
```
cd C:\Users\thefi\slab-library\tools
python harvest_bloomstones2.py            # re-crawl (cached; safe to re-run)
python reconcile_bloomstones2.py --report # match/selection table, no writes
python reconcile_bloomstones2.py --apply  # downloads + patch_library(supplier="Bloomstones")
```
Cache: `tools/_cache/bloomstones2/` (pages + downloaded originals + manifest.json).
Originals: OneDrive `1. QUARTZ\Bloomstone quartz\<Colour>\` and
`3. CERAMIC- PORCELAIN\Bloomstone\<Colour>\`.
Contact sheet: `tools/_reports/bloomstones2-galleries.png` (53 images, all
additions — no mains changed so no mains sheet was generated).

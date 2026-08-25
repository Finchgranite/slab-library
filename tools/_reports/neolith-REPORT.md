# Neolith harvest report (galleries pass)

Sources used this run (see `harvest_neolith.py` docstring for full diligence trail):
1. **Neolith UK official asset zip** (already in OneDrive
   `3. CERAMIC- PORCELAIN\Neolith\laurelcomms_full-uk-neolith-colour-collection_2026-03-31_0945.zip`,
   dated Jan 2026) -- slab photos for Black Obsession and Cappadocia Sunset,
   which are confirmed DELISTED from the current neolith.com `/en/all-colours`
   (no "black"/"cappadocia" string anywhere in that page's data payload) --
   the zip is the only source, `productUrl` left blank for these two.
2. **neolith.com live fetch** (curl, NOT bot-blocked -- returns 200 SSR HTML,
   contrary to the 2026-08-24 Thomas Group discovery note) -- Calacatta Roma
   and Everest Sunrise DO still have live pages (`classtone/calacatta-roma/`,
   `classtone/everest-sunrise/`) that the library had simply never recorded;
   their Storyblok full-res originals were fetched directly (2000x3945 and
   1250x1824) rather than using the zip's lower-res copies.
3. **Brochure PDF** (inside the same zip) -- one room photo, Himalaya
   Crystal, London private residence (1009x771, page 7 of 17). Everything
   else image-sized in the brochure is either an awards-logo montage or a
   swatch grid under 300px wide (skipped per spec rule 3).
4. **Price book** (`hl.load_pricebook("Neolith")`) -- exact 1:1 match against
   all 45 library colours (no unmatched names either direction) -- supplied
   `slabSizes` and (with the collection parsed from `productUrl`) `details`
   for every entry that lacked one.

## Counts
- Neolith library entries: 45 (all engineered, none touched outside this supplier)
- Mains newly filled (was `missing`): 4 / 4 -- ['Black Obsession', 'Calacatta Roma (BM)', 'Cappadocia Sunset', 'Everest Sunrise']
- Still `missing` after this run: none
- Room images added: 1 (Himalaya Crystal)
- Closeup images already present (unchanged, from an earlier Thomas Group run): 5
  (Beton, Calacatta (BM), Calacatta Gold (BM), Estatuario (BM), Zaha Stone)
- Entries with `slabSizes`/`details` newly filled: 45
- Entries with no gallery (`images[]`) at all after this run: 39 / 45

## Image source per new asset
- Black Obsession, Cappadocia Sunset: Neolith UK official asset zip (slab)
- Calacatta Roma (BM), Everest Sunrise: neolith.com live Storyblok fetch (slab)
- Himalaya Crystal: Neolith UK Brochure PDF, page 7 (room)

## Blocked / unavailable for galleries (orchestrator browser-pass candidates)
Every colour whose gallery is still empty (all 45 minus the 5 Thomas-Group-linked ones, plus Himalaya Crystal's new room) has NO curl-fetchable closeup/room source: neolith.com's product pages (and their Nuxt static state.js/payload.js sidecars) carry exactly one photo -- the slab -- with the rest of the gallery hydrated by a live runtime API call; thesurfacecollection.co.uk's Neolith page only covers 16 different colourways of which 5 already overlap our library. A claude-in-chrome pass on neolith.com product pages (or the /en/neolith-projects/ grid, JS-rendered) is the only way to get closeup/room images for the other ~39 colours.

## Assumptions
- Black Obsession and Cappadocia Sunset have no confirmed current
  neolith.com collection (their live pages 403 on every `classtone/<slug>/`
  guess tried, and they don't appear in `/en/all-colours` at all) -- their
  `details` line omits a collection name ("Neolith sintered stone" instead
  of e.g. "Neolith Classtone collection"); worth confirming with Neolith UK
  whether these are simply discontinued.
- Price book is the sizing/naming authority throughout; no Thomas Group
  fallback was needed since all 45 Neolith price-book rows matched the
  library 1:1.

## Re-run
```
python tools/harvest_neolith.py             # re-extract/fetch (cached under tools/_cache/neolith/)
python tools/reconcile_neolith.py --report   # dry run, prints the plan
python tools/reconcile_neolith.py --apply    # writes images/ + slabs.json
```

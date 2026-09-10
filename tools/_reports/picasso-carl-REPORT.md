# Picasso Surfaces — Carl Kimpton (Quantum Stone) Google Drive photo pack import (2026-09-10)

Source: Carl's Drive folder https://drive.google.com/drive/folders/15pozW0r8SJF6TEbwkZnk3iKDvfotQwFC (one sub-folder per colour, files dated Mar/Apr 2026), sent 2026-09-10
in reply to Graham's 5 Sep email. Downloaded with gdown; not a website harvest.
Script: `tools/picasso_carl_import.py --src <folder> --report` then `--apply`.

## Counts
- Drive colour folders: **46** (matched to Picasso entries: **41**, unmatched: **5**)
- Mains set/replaced: **3** (of which UPGRADED from a tiny web image: **2**) — Grey Mirror (slab 750px→upgrade), Viola (missing 0px→slab), White Mirror (slab 750px→upgrade)
- Entries whose site main was kept (Carl's slab shots added as `kind: slab` `--alt` images): **38**
- Extra slab images: **82** · closeups: **12** · rooms: **60**
- Unmatched folders (in Carl's pack but not a Picasso price-book colour): **5** — Silver Cloud, Symphony Ice Age HD Printed, Symphony Taj Mahal HD Printed, Symphony Water shadow, Symphony Winter field
- Picasso entries STILL without a `status: slab` main: **1** — Verde Tempsta

## Kind classification
bare colour-name / `HQ` / `(2)` stems = slab (main candidate); `rack` / `on rack` = slab on an A-frame (kind: slab alt, never a main);
`Detail` / `Close` = closeup; `Kitchen` / `install` / `Island` / `worktop` / `countertop` / an `INSTALL` sub-folder / portrait aspect = room;
`LQ` = skipped (low-res duplicate); `.tif` = OneDrive only. Dedupe by SHA-256 (the two Arabescato Creme folders share one rack shot).
Main upgrade rule: current main < 1000 px wide AND Carl sent a slab face → Carl's becomes the main, the old one stays as an alt.
Per-file overrides: `Annapurna/Annapurna.JPEG` → room; `Cashmere/Cashmere (3).jpg` → room; `Cashmere/Cashmere (4).jpg` → room; `Cashmere/Cashmere (5).jpg` → room; `Cashmere/Cashmere (6).jpg` → room; `Cashmere/Cashmere (7).jpg` → room; `Cashmere/Cashmere racking.JPG` → rack; `Celestial Grey/Celestial Grey 1.jpg` → room; `Celestial Grey/Celestial Grey 2.jpg` → room; `Celestial White/Celestial White 1.jpg` → room; `Celestial White/Celestial White 2.jpg` → room; `Cristallo/Cristallo- (1).jpg` → room; `Cristallo/Cristallo- (3).jpg` → room; `Orella/Orella (1).jpg` → room; `Patagonia/Patagonia  (1).JPEG` → room; `Solarius/Solarius  (1).jpg` → room; `Viola/Viola  (1).jpeg` → closeup; `Viola/Viola  (4).jpeg` → closeup; `Verde Onyx/Verde Onyx (2).jpg` → rack.

## Name mapping (Drive folder → library colour)
arabescato creme matte → Arabescato Creme, arabescato crème polished → Arabescato Creme, arabescato creme polished → Arabescato Creme, royal cream polished → Crema Royal, royal creme matte → Crema Royal, snowdale (white shimmer) → Snowdale, taj onyx → Taj Honey Onyx, taj mahal extra matte → Taj Mahal Extra, taj mahal extra polished → Taj Mahal Extra, sunlight matte → Sunlight, white lake matte → White Lake, himalyan pink onyx → Himalyan Pink Onyx, himalayan pink onyx → Himalyan Pink Onyx, jade galcia → Jade Glacia, carrara gold → Calacatta Gold

## Notes / to ask Carl (draft reply already in Graham's Outlook Drafts, 2026-09-10)
- Carl's `Carrara Gold/` folder holds files named `Calacatta Gold ...` — imported to **Calacatta Gold**; Carrara Gold got nothing. Ask for a Carrara Gold slab shot.
- **Verde Tempesta** (price book spells it `Verde Tempsta`): Carl — "photos will be available soon, this isn't due to arrive until November" (2026). Still `missing`; not discontinued.
- **Viola**: 5 photos in the pack (main set from the 8268 px slab face) but NOT in the 2026 brochure — availability asked.
- **White Mirror / Grey Mirror**: one photo each in the pack AND in the 2026 brochure (OneDrive `North Picasso Surfaces Brochure 2026.pdf`) — current; both 750 px old-site mains upgraded.
- **Black Mirror / Calacatta Gold**: their Drive folders are EMPTY (Calacatta Gold's photos sit in the `Carrara Gold/` folder); neither is in the 2026 brochure, nor is Carrara Gold — photos + availability asked. Black Mirror keeps its 750 px old-site main.
- **Silver Cloud**: in the pack + brochure, not in the price book — copied to `_unmatched` only.
- **Symphony HD Print** (Taj Mahal / Ice Age / Water shadow / Winter field): in the pack + 2026 brochure, NOT in the price book → copied to `_unmatched` only; price band + slab size asked.
- Site-harvest `scale` is not set on Carl's images (studio / A-frame shots; not true-scale).
- Closeups capped at 4, rooms at 4 new per entry; skipped: Arctic Storm: 0 cu / 2 rm; Carrara Neo: 0 cu / 2 rm; Cashmere: 0 cu / 3 rm; Golden Thunder: 0 cu / 1 rm; Sunlight: 0 cu / 4 rm; White Lake: 0 cu / 2 rm.

## Re-run
```
cd tools
python picasso_carl_import.py --src "<downloaded folder>" --report
python picasso_carl_import.py --src "<downloaded folder>" --apply   # idempotent; rebuilds Carl-sourced items
```
Originals: OneDrive `1. QUARTZ\Quantum & Picasso Quartz\<Colour>\_from Carl 2026-09-10\`. Contact sheets: `picasso-carl-mains.png`, `picasso-carl-galleries.png`.

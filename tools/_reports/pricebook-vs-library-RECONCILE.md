# Price book vs slab library — reconciliation (2026-08-24 evening)

Scope: ENGINEERED colours only (quartz / porcelain / sintered / ceramic). Natural stone excluded by Graham's rule.

## Price-book colours with no library entry
- 2,486 unique (supplier, colour) in the price book; 2,114 join a library entry on name; 372 do not:
  - **Thomas Group (Surfaces Collection): 224** — whole supplier absent. Engineered 157 = 76 Porcelain (Atlas Plan), 65 Quartz, 16 Sintered. → discovery agent running.
  - **B-Stone: 146** — 142 natural (out of scope), **4 engineered to add: Cadiz, Colossal Cream, Forest, Salina Ivory**.
  - Picasso "Golden Thunder" = library "Thunder Gold"; IQ "Calacatta Magma Silver" = library "Calacatta Skylight" → `aliases` added 2026-08-24.

## Engineered coverage per supplier (library) + site domain seen in productUrl

| Supplier | entries | slab main | closeup-only | missing | gallery | site (from productUrl) |
|---|---|---|---|---|---|---|
| Bloomstones | 117 | 83 | 0 | 34 | 0 | www.bloomstoneslondon.com (80) |
| CRL | 109 | 91 | 12 | 6 | 0 | crlstone.co.uk (103) |
| International Stones (IQ) | 107 | 96 | 3 | 8 | 0 | www.istones.co.uk (57), materiaslab.com (21) |
| Quartzforms | 100 | 98 | 0 | 1 | 0 | www.quartzforms.com (100) |
| Cosentino Dekton | 94 | 70 | 0 | 24 | 0 | www.cosentino.com (63) |
| Clay International | 78 | 75 | 0 | 3 | 0 | clayinternational.co.uk (72) |
| Caesarstone | 76 | 52 | 11 | 13 | 0 | www.caesarstone.co.uk (44) |
| Cosentino Silestone | 74 | 70 | 1 | 3 | 0 | www.cosentino.com (49) |
| UK Stone Company | 54 | 27 | 1 | 26 | 0 | www.ukstonecompany.com (28) |
| World Wide Stones | 54 | 42 | 6 | 6 | 0 | www.worldwidestones.co.uk (45) |
| Nile Stone | 52 | 46 | 0 | 6 | 0 | — |
| AKG Surfaces | 49 | 49 | 0 | 0 | 0 | akgsurfaces.co.uk (49) |
| Technistone | 49 | 49 | 0 | 0 | 0 | www.technistone.com (49) |
| Fugen | 46 | 32 | 2 | 12 | 0 | www.fugenstone.co.uk (33) |
| Picasso Surfaces | 46 | 28 | 1 | 17 | 0 | www.picassostones.com (21) |
| Neolith | 45 | 41 | 0 | 4 | 0 | www.neolith.com (41) |
| RT Stone | 44 | 37 | 1 | 6 | 0 | www.quartzbyrtstone.co.uk (38) |
| BQS | 43 | 40 | 0 | 3 | 0 | — |
| Compac | 36 | 34 | 2 | 0 | 0 | en.compac.es (32) |
| Brachot | 35 | 35 | 0 | 0 | 0 | — |
| Kingstone | 35 | 22 | 0 | 13 | 0 | kingstonequartz.co.uk (22) |
| Unistone | 33 | 32 | 0 | 1 | 0 | — |
| B-Stone | 32 | 26 | 1 | 4 | 0 | bstoneuk.co.uk (4) |
| KSG | 31 | 19 | 0 | 12 | 0 | — |
| LuxeStone | 22 | 0 | 0 | 22 | 0 | — |
| Lumina Stone | 18 | 6 | 1 | 11 | 0 | — |
| Quartz Hub | 15 | 14 | 1 | 0 | 0 | www.quartzhub.co.uk (14) |
| Sapien Stone | 1 | 1 | 0 | 0 | 0 | — |

## Fan-out priority (value per token)
1. Caesarstone (pilot, builds harvest_lib) · 2. Thomas Group / Atlas Plan (157 new) · 3. LuxeStone (22/22 missing, no URLs) · 4. Cosentino Dekton (24) + Silestone (galleries) · 5. Bloomstones (34) · 6. UK Stone Co (26) · 7. Picasso (17) · 8. Kingstone (13) · 9. Fugen (12) · 10. KSG (12) · 11. Lumina (11) · 12. IQ (8) · 13. Quartzforms / Technistone / Neolith / Unistone / CRL / Compac / Clay / AKG / BQS / RT / WWS / Nile / Brachot / Quartz Hub — mains mostly present; galleries + sizes/details only. B-Stone 4 engineered.

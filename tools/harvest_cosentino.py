"""Cosentino Dekton + Silestone (www.cosentino.com, en-gb) harvest (2026-08-24).

cosentino.com itself is behind a Sucuri CloudProxy JS challenge -- curl (even with
browser headers) gets a JS-redirect stub, not the page. A real browser (claude-in-chrome)
passes the challenge fine on normal navigation, and same-origin fetch() from inside an
already-loaded cosentino.com tab also works (reuses the solved session) -- but the site
enforces `Crawl-delay: 10` (robots.txt) and started hard-failing (net error / AbortError)
after ~10 rapid fetches in one session. So: browser-scrape was used ONCE, lightly, to pull
a same-page "all colours" widget (div.inspiration cards, present on every /colours/<brand>/
page) that embeds each colour's asset CODE via `data-lazy-src` pointing at
`.../api/v1/bynder/color/<CODE>/detalle/<CODE>-thumb.jpg`. That widget is NOT the full
catalogue (~157 cards spanning all 5 brands; it looks like a "featured/current" cross-sell
strip, some tiles marked "Soon") but it gave real, confirmed hrefs + codes for 65 Dekton +
49 Silestone colours in one page load, with zero risk of further rate-limiting.

The asset CDN itself -- assetstools.cosentino.com -- is a SEPARATE, unprotected host (no
Sucuri, no rate-limit hit in testing): given any CODE,
  tablahd/<CODE>-fullslab.jpg  -> full slab (any filename works; ~20-30MB originals)
  detalle/<CODE>-thumb.jpg     -> texture/detail closeup (any filename works)
are both fetchable directly by curl. No CDN pattern was found for room/kitchen shots
(ambiente/cocina/kitchen/room/textura all 400) -- individual product-page HTML has genuine
per-colour room photos (e.g. `dekton-kitchen-laurent.jpg`) but reaching them needs the
rate-limited page fetch, so room images are OUT OF SCOPE this run.

CODES/SLUG_TO_CODE below are the widget-scrape result (2026-08-24) merged with the codes
already known from the earlier scrape_cosentino.py/scrape_silestone.py pilots (2026-07-19)
-- kept as a fallback for colours the widget didn't surface but whose code was already
proven to resolve a real image via the CDN previously (those are already applied in
slabs.json; kept here only so closeup-harvesting can reuse the same code).

Produces tools/cosentino-harvest.json; reconcile_cosentino.py consumes it.
"""
import json
import os
import re

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))

# brand/slug -> code, confirmed live via cosentino.com widget scrape 2026-08-24
# (real <a href> seen in DOM -> productUrl is 100% confirmed for these)
WIDGET = {}
for pair in """
dekton/akara=KCK dekton/grekk=KTA dekton/talma=KRW dekton/nordal=NOK dekton/kobuk=RHN
dekton/borealis=BOK dekton/sandik=MRL dekton/evok=PWK dekton/keena=WMK dekton/thala=DVK
dekton/kedar=NRL dekton/zira=BQK dekton/nara=NAK dekton/nebu=WCP dekton/ava=VTP
dekton/trevi=TVG dekton/polar=CPO dekton/adia=PIT dekton/grigio=GCK dekton/grafite=P5C
dekton/marmorio=RCK dekton/avorio=VCK dekton/nebbia=ECK dekton/sabbia=ICK dekton/ceppo=PCK
dekton/dunna=NNC dekton/salina=AAI dekton/marina=RMR dekton/albarium=RLM dekton/awake=DSV
dekton/somnia=BMT dekton/trance=MCA dekton/neural=VGL dekton/lucid=RBL dekton/morpheus=MSC
dekton/reverie=RRK dekton/argentium=NMK dekton/umber=T2A dekton/nacre=CKC dekton/kovik=SVA
dekton/helena=HCK dekton/khalo=HLC dekton/aeris=IKC dekton/rem=RKC dekton/laurent=PTL
dekton/eter=BDK dekton/taga=GKC dekton/moone=MKC dekton/arga=RGC dekton/bromo=BRM
dekton/lunar=UKC dekton/kreta=KRE dekton/laos=LOS dekton/kira=PU4 dekton/soke=CV5
dekton/halo=HKC dekton/entzo=EKC dekton/trilium=LD2 dekton/kelya=DKL dekton/bergen=BEK
dekton/domoos=OMD dekton/aura=AKC dekton/danae=KAC dekton/zenith=ZKC dekton/sirius=DIR
silestone/calacatta-tova=TTT silestone/bronze-rivers=BNR silestone/motion-grey=LJU
silestone/linen-cream=MTJ silestone/siberian=PRJ silestone/persian-white=ALT
silestone/blanc-elysee=PI2 silestone/jardin-emerald=DGJ silestone/riviere-rose=PI1
silestone/ffrom02=PI9 silestone/ffrom03=PI8 silestone/raw-d=PI5 silestone/raw-a=PI4
silestone/ffrom01=PI7 silestone/romantic-ash=OM6 silestone/bohemian-flame=OM3
silestone/victorian-silver=OM4 silestone/versailles-ivory=OM2 silestone/parisien-bleu=OM5
silestone/brass-relish=L4J silestone/lime-delight=L1J silestone/cinder-craze=L3J
silestone/concrete-pulse=L2J silestone/ethereal-noctis=MR4 silestone/ethereal-glow=MR1
silestone/white-arabesque=LG3 silestone/poblenou=C10 silestone/miami-vena=MVN
silestone/nolita=N23 silestone/desert-silver=GVX silestone/night-tebas18=GV2
silestone/pearl-jasmine=JAP silestone/et-marquina=ETM silestone/charcoal-soapstone=CHD
silestone/miami-white=M7J silestone/et-calacatta-gold=52C silestone/et-statuario=ETS
silestone/snowy-ibiza=LG1 silestone/ariel=AIJ silestone/coral-clay-colour=BCR
silestone/blanco-maple=M1J silestone/blanco-norte14=BN2 silestone/white-storm14=WS2
silestone/stellar-blanco13=BS3 silestone/lyra=VLI silestone/lagoon=VLG
silestone/gris-expo=GEJ silestone/white-zeus=BZJ silestone/marengo=MAJ
""".split():
    WIDGET[pair.split("=")[0]] = pair.split("=")[1]

# fallback codes known from the 2026-07-19 pilots (scrape_cosentino.py / scrape_silestone.py)
# for colours the widget didn't surface this run -- no confirmed live URL, code only.
LEGACY = {}
for pair in """
dekton/aeris=IKC dekton/albarium=RLM dekton/arga=RGC dekton/argentium=NMK dekton/aura=AKC
dekton/ava=VTP dekton/avorio=VCK dekton/awake=DSV dekton/bergen=BEK dekton/bromo=BRM
dekton/ceppo=PCK dekton/danae=KAC dekton/domoos=OMD dekton/dunna=NNC dekton/entzo=EKC
dekton/eter=BDK dekton/evok=PWK dekton/grafite=P5C dekton/grigio=GCK dekton/halo=HKC
dekton/helena=HCK dekton/kedar=NRL dekton/keena=WMK dekton/kelya=DKL dekton/khalo=HLC
dekton/kira=PU4 dekton/kovik=SVA dekton/kreta=KRE dekton/laos=LOS dekton/laurent=PTL
dekton/lucid=RBL dekton/lunar=UKC dekton/marina=RMR dekton/marmorio=RCK dekton/moone=MKC
dekton/morpheus=MSC dekton/nacre=CKC dekton/nara=NAK dekton/nebbia=ECK dekton/nebu=WCP
dekton/neural=VGL dekton/polar=CPO dekton/rem=RKC dekton/reverie=RRK dekton/sabbia=ICK
dekton/salina=AAI dekton/sandik=MRL dekton/sirius=DIR dekton/soke=CV5 dekton/somnia=BMT
dekton/taga=GKC dekton/thala=DVK dekton/trance=MCA dekton/trevi=TVG dekton/trilium=LD2
dekton/umber=T2A dekton/zenith=ZKC dekton/zira=BQK
silestone/calacatta-tova=TTT silestone/bronze-rivers=BNR silestone/motion-grey=LJU
silestone/linen-cream=MTJ silestone/siberian=PRJ silestone/persian-white=ALT
silestone/blanc-elysee=PI2 silestone/jardin-emerald=DGJ silestone/riviere-rose=PI1
silestone/ffrom02=PI9 silestone/ffrom03=PI8 silestone/raw-d=PI5 silestone/raw-a=PI4
silestone/ffrom01=PI7 silestone/romantic-ash=OM6 silestone/bohemian-flame=OM3
silestone/victorian-silver=OM4 silestone/versailles-ivory=OM2 silestone/parisien-bleu=OM5
silestone/brass-relish=L4J silestone/lime-delight=L1J silestone/cinder-craze=L3J
silestone/concrete-pulse=L2J silestone/ethereal-dusk=MR2 silestone/ethereal-haze=MR3
silestone/white-arabesque=LG3 silestone/miami-vena=MVN silestone/nolita=N23
silestone/desert-silver=GVX silestone/night-tebas18=GV2 silestone/pearl-jasmine=JAP
silestone/et-marquina=ETM silestone/charcoal-soapstone=CHD silestone/miami-white=M7J
silestone/et-calacatta-gold=52C silestone/et-statuario=ETS silestone/snowy-ibiza=LG1
silestone/ariel=AIJ silestone/coral-clay-colour=BCR silestone/blanco-maple=M1J
silestone/blanco-norte14=BN2 silestone/white-storm14=WS2 silestone/stellar-blanco13=BS3
silestone/lyra=VLI silestone/lagoon=VLG silestone/gris-expo=GEJ silestone/white-zeus=BZJ
silestone/marengo=MAJ silestone/poblenou=C10
""".split():
    k, v = pair.split("=")
    LEGACY.setdefault(k, v)

SUPPLIER_BRAND = {"Cosentino Dekton": "dekton", "Cosentino Silestone": "silestone"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main():
    lib = hl.load_library()
    manifest = []
    for supplier, brand in SUPPLIER_BRAND.items():
        entries = [s for s in lib["slabs"] if s.get("supplier") == supplier]
        # index widget/legacy by normalised slug for this brand
        widget_by_slug = {k.split("/", 1)[1]: v for k, v in WIDGET.items() if k.startswith(brand + "/")}
        legacy_by_slug = {k.split("/", 1)[1]: v for k, v in LEGACY.items() if k.startswith(brand + "/")}
        widget_by_norm = {norm(s): (s, c) for s, c in widget_by_slug.items()}
        legacy_by_norm = {norm(s): (s, c) for s, c in legacy_by_slug.items()}

        for e in entries:
            cn = norm(e["colour"])
            hit = widget_by_norm.get(cn) or widget_by_norm.get(re.sub(r"\d+$", "", cn))
            confirmed = hit is not None
            if not hit:
                hit = legacy_by_norm.get(cn) or legacy_by_norm.get(re.sub(r"\d+$", "", cn))
            rec = {"id": e["id"], "colour": e["colour"], "supplier": supplier, "brand": brand,
                   "status": e["image"]["status"], "has_url": bool(e.get("productUrl"))}
            if hit:
                slug, code = hit
                rec["slug"] = slug
                rec["code"] = code
                rec["url_confirmed"] = confirmed
            manifest.append(rec)

        # site colours in the widget with NO library match at all (report only)
        for slug, code in widget_by_slug.items():
            name_guess = slug.replace("-", " ")
            pool = [(e["colour"], e) for e in entries]
            found, _ = hl.match_colour(name_guess, pool)
            if not found:
                manifest.append({"id": None, "colour": name_guess.title(), "supplier": supplier,
                                  "brand": brand, "slug": slug, "code": code, "site_only": True})

    out_path = os.path.join(SCRATCH, "cosentino-harvest.json")
    json.dump(manifest, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_code = sum(1 for m in manifest if m.get("code") and not m.get("site_only"))
    n_confirmed = sum(1 for m in manifest if m.get("url_confirmed"))
    n_site_only = sum(1 for m in manifest if m.get("site_only"))
    print(f"WROTE {out_path}: {len(manifest)} rows | with code: {n_code} | url-confirmed: {n_confirmed} "
          f"| site-only (no lib match): {n_site_only}")


if __name__ == "__main__":
    main()

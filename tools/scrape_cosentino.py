"""Download full-slab images from Cosentino's asset CDN for a given brand.

Codes harvested from cosentino.com/en-gb/colours/ catalogue cards (2026-07-19).
Full slab: assetstools.cosentino.com/api/v1/bynder/color/{CODE}/tablahd/{CODE}-fullslab.jpg

Usage: python tools/scrape_cosentino.py "Cosentino Dekton" dekton
Sensa/Scalea codes are natural-stone brands kept for the granite phase
(match by colour name across suppliers, per the shared-image rule).
"""
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # trusted supplier CDN; some HD slabs exceed PIL's default cap

REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
MAX_WIDTH = 1600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

CODES = {}
for pair in """
dekton/adia=PIT dekton/aeris=IKC dekton/albarium=RLM dekton/arga=RGC dekton/argentium=NMK
dekton/aura=AKC dekton/ava=VTP dekton/avorio=VCK dekton/awake=DSV dekton/bergen=BEK
dekton/bromo=BRM dekton/ceppo=PCK dekton/danae=KAC dekton/domoos=OMD dekton/dunna=NNC
dekton/entzo=EKC dekton/eter=BDK dekton/evok=PWK dekton/grafite=P5C dekton/grigio=GCK
dekton/halo=HKC dekton/helena=HCK dekton/kedar=NRL dekton/keena=WMK dekton/kelya=DKL
dekton/khalo=HLC dekton/kira=PU4 dekton/kovik=SVA dekton/kreta=KRE dekton/laos=LOS
dekton/laurent=PTL dekton/lucid=RBL dekton/lunar=UKC dekton/marina=RMR dekton/marmorio=RCK
dekton/moone=MKC dekton/morpheus=MSC dekton/nacre=CKC dekton/nara=NAK dekton/nebbia=ECK
dekton/nebu=WCP dekton/neural=VGL dekton/polar=CPO dekton/rem=RKC dekton/reverie=RRK
dekton/sabbia=ICK dekton/salina=AAI dekton/sandik=MRL dekton/sirius=DIR dekton/soke=CV5
dekton/somnia=BMT dekton/taga=GKC dekton/thala=DVK dekton/trance=MCA dekton/trevi=TVG
dekton/trilium=LD2 dekton/umber=T2A dekton/zenith=ZKC dekton/zira=BQK
sensa/black-beauty=BBT sensa/colonial-white=COW sensa/cristalo=ZIA sensa/glacial-blue=GLA
sensa/ice-blue19=IBL sensa/indian-black=132 sensa/itara=TIZ sensa/marau=RUA
sensa/moak-black=MCK sensa/nahoa=NAH sensa/nilo=NIL sensa/oihana=OHN sensa/orinoco=JPB
sensa/platino=PTN sensa/sant-angelo=SNL sensa/siberia=SBE sensa/taj-mahal=TAK
sensa/vancouver=VNC sensa/white-macaubas=181
scalea/andromeda=AND scalea/belvedere=BVD scalea/blanco-ibiza=9E scalea/calacatta-ice=CTI
scalea/calacatta-lincon=CLI scalea/caliza-capri=C1 scalea/caliza-nevada=CQ
scalea/crema-marfil=CF scalea/crema-moca=DI scalea/elegant-grey=EGY scalea/gris-pulpis=PU
scalea/jura-blue-grey=JBG scalea/negresco=NEG scalea/perlado=PE
eclos/ivora=DAV eclos/landr=RAL eclos/legnd=EMO eclos/lumer=OJB eclos/phantome=PHM
eclos/sandr=EDO eclos/tajnar=TAW eclos/vancor=VJU eclos/veilr=VEJ eclos/wondr=WON
""".split():
    key, code = pair.split("=")
    brand, slug = key.split("/")
    CODES.setdefault(brand, {})[slug] = code


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main():
    supplier, brand = sys.argv[1], sys.argv[2]
    codes = CODES[brand]
    by_norm = {norm(slug): (slug, code) for slug, code in codes.items()}
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    targets = [s for s in db["slabs"] if s["supplier"] == supplier]
    ok = skipped = fail = 0
    for e in targets:
        if e["image"].get("source") == "cosentino.com":
            ok += 1
            continue
        cn = norm(e["colour"])
        hit = by_norm.get(cn) or by_norm.get(re.sub(r"\d+$", "", cn))
        if not hit:
            skipped += 1
            continue
        slug, code = hit
        try:
            url = f"https://assetstools.cosentino.com/api/v1/bynder/color/{code}/tablahd/{code}-fullslab.jpg"
            r = requests.get(url, timeout=90, headers=UA)
            r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
            fname = f"{e['id']}.webp"
            im.save(IMAGES_DIR / fname, "WEBP", quality=82)
            e["image"] = {"file": fname, "status": "slab", "source": "cosentino.com", "borrowedFrom": ""}
            if not e.get("productUrl"):
                e["productUrl"] = f"https://www.cosentino.com/en-gb/colours/{brand}/{slug}/"
            ok += 1
            time.sleep(0.4)
        except Exception as ex:
            print(f"FAIL {e['colour']} ({code}): {ex}")
            fail += 1
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{supplier} via {brand}: {ok} ok, {skipped} not on site, {fail} failed")


if __name__ == "__main__":
    main()

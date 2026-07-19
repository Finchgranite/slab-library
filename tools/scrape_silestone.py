"""Download official full-slab images for Silestone from Cosentino's asset CDN.

Colour codes were harvested from cosentino.com/en-gb/colours/ card thumbnails
(2026-07-19). Full slab: assetstools.cosentino.com/api/v1/bynder/color/{CODE}/tablahd/{CODE}-fullslab.jpg
"""
import json
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
MAX_WIDTH = 1600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

SLUG_TO_CODE = dict(p.split("=") for p in """calacatta-tova=TTT bronze-rivers=BNR motion-grey=LJU
linen-cream=MTJ siberian=PRJ persian-white=ALT blanc-elysee=PI2 jardin-emerald=DGJ riviere-rose=PI1
ffrom02=PI9 ffrom03=PI8 raw-d=PI5 raw-a=PI4 ffrom01=PI7 romantic-ash=OM6 bohemian-flame=OM3
victorian-silver=OM4 versailles-ivory=OM2 parisien-bleu=OM5 brass-relish=L4J lime-delight=L1J
cinder-craze=L3J concrete-pulse=L2J ethereal-noctis=MR4 ethereal-glow=MR1 white-arabesque=LG3
poblenou=C10 miami-vena=MVN nolita=N23 desert-silver=GVX night-tebas18=GV2 pearl-jasmine=JAP
et-marquina=ETM charcoal-soapstone=CHD miami-white=M7J et-calacatta-gold=52C et-statuario=ETS
snowy-ibiza=LG1 ariel=AIJ coral-clay-colour=BCR blanco-maple=M1J blanco-norte14=BN2
white-storm14=WS2 stellar-blanco13=BS3 lyra=VLI lagoon=VLG gris-expo=GEJ white-zeus=BZJ
marengo=MAJ""".split())

# price-book name -> site slug where they differ beyond digits/spacing
ALIASES = {"blancozeus": "white-zeus"}
# pattern-guessed codes, downloaded as guess-*.webp for visual verification only
GUESSES = {"Ethereal Dusk": "MR2", "Ethereal Haze": "MR3"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def code_for(colour):
    cn = norm(colour)
    if cn in ALIASES:
        return SLUG_TO_CODE[ALIASES[cn]]
    by_norm = {norm(slug): code for slug, code in SLUG_TO_CODE.items()}
    if cn in by_norm:
        return by_norm[cn]
    base = re.sub(r"\d+$", "", cn)  # Miami White17 -> miami-white
    return by_norm.get(base)


def fetch_slab(code):
    url = f"https://assetstools.cosentino.com/api/v1/bynder/color/{code}/tablahd/{code}-fullslab.jpg"
    r = requests.get(url, timeout=90, headers=UA)
    r.raise_for_status()
    im = Image.open(BytesIO(r.content)).convert("RGB")
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    return im


def main():
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    targets = [s for s in db["slabs"] if s["supplier"] == "Cosentino Silestone"]
    ok = skipped = fail = 0
    for e in targets:
        code = code_for(e["colour"])
        if not code:
            skipped += 1
            continue
        try:
            im = fetch_slab(code)
            fname = f"{e['id']}.webp"
            im.save(IMAGES_DIR / fname, "WEBP", quality=82)
            e["image"] = {"file": fname, "status": "slab", "source": "cosentino.com", "borrowedFrom": ""}
            if not e.get("productUrl"):
                slug = ALIASES.get(norm(e["colour"])) or next(
                    (s for s, c in SLUG_TO_CODE.items() if c == code), "")
                if slug:
                    e["productUrl"] = f"https://www.cosentino.com/en-gb/colours/silestone/{slug}/"
            print(f"OK   {e['colour']} ({code})")
            ok += 1
            time.sleep(0.4)
        except Exception as ex:
            print(f"FAIL {e['colour']} ({code}): {ex}")
            fail += 1
    for colour, code in GUESSES.items():
        try:
            im = fetch_slab(code)
            im.save(IMAGES_DIR / f"guess-{norm(colour)}-{code}.webp", "WEBP", quality=82)
            print(f"GUESS downloaded: {colour} ({code}) -> guess-{norm(colour)}-{code}.webp (verify before use)")
        except Exception as ex:
            print(f"GUESS failed: {colour} ({code}): {ex}")
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {ok} ok, {skipped} not on site, {fail} failed")


if __name__ == "__main__":
    main()

"""Pattern-based slab scraper for suppliers with predictable image URLs.

Each supplier config yields (candidate_image_urls, product_url) per colour.
Run: python tools/scrape_patterns.py "International Stones (IQ)"
"""
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO = Path(__file__).resolve().parent.parent
SLABS_JSON = REPO / "slabs.json"
IMAGES_DIR = REPO / "images"
MAX_WIDTH = 1600
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def iq_urls(colour, material):
    slug = slugify(re.sub(r"\d+$", "", colour.strip()))
    mats = [material.lower(), "quartz", "granite", "quartzite", "marble", "limestone", "ceramic"]
    seen, cands = set(), []
    for m in mats:
        if m in seen:
            continue
        seen.add(m)
        cands.append((f"https://www.istones.co.uk/images/{m}/slabs/{slug}-320x160-crop.png",
                      f"https://www.istones.co.uk/{m}/{slug}.html"))
    return cands


def wp_media(domain):
    """WordPress media-API strategy: search the media library by colour name,
    keep slab-shaped images whose filename starts with the colour slug."""
    def gen(colour, material):
        base = re.sub(r"\d+$", "", colour.strip()).strip()
        try:
            r = requests.get(f"https://{domain}/wp-json/wp/v2/media",
                             params={"search": base, "per_page": 40}, timeout=30, headers=UA)
            items = r.json() if r.status_code == 200 else []
        except Exception:
            items = []
        slug = slugify(base)
        scored = []
        for m in items:
            u = m.get("source_url", "")
            det = m.get("media_details", {})
            w, h = det.get("width", 0), det.get("height", 0)
            fname = slugify(u.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            if not fname.startswith(slug):
                continue
            if any(b in fname for b in ("kitchen", "room", "worktop", "install", "logo", "brochure")):
                continue
            s = 0
            if h and 1.5 <= w / h <= 2.7:
                s += 50
            s += min(w, 3000) / 100
            scored.append((s, u))
        scored.sort(reverse=True)
        return [(u, f"https://{domain}/?s={base.replace(' ', '+')}") for _, u in scored[:3]]
    return gen


TECHNISTONE_IDS = dict(p.split("=") for p in """altamonte=68 badal-grey=85 brilliant-arabesco=30
brilliant-black=4 brilliant-white=2 bronze-coast=69 calacatta-aurelia=91 calacatta-olympos=61
calacatta-serchio=60 calacatta-volegno=1 crystal-absolute-white=13 crystal-diamond=15
crystal-nevada=16 crystal-polar-white=14 crystal-royal=17 duna-beige=86 dynasty-white=94
elegance-eco-nev=29 elysian-gold=87 emperador-beige=92 glencoe=71 gobi-black=20 gobi-urban=44
harmonia-navajo=62 mistral-white=89 morning-daisy=79 mystery-white=39 noble-arco-gold=98
noble-arco=43 noble-areti-bianco=28 noble-athos-brown=22 noble-carrara=76 noble-concrete-grey=23
noble-ivory-white=25 noble-olympos-mist=26 noble-pietra-grey=27 noble-portland-grey=58
noble-pro-cloud=32 noble-pro-frost=31 noble-pro-storm=33 noble-quartzite=54 noble-supreme-brass=102
noble-supreme-white=9 noble-vintage=57 pearl-delta=49 perlado-bronze=93 residente-dark=46
starlight-black=8 starlight-white=3 taj-mahal-gold=88 taurus-black=21 taurus-terazzo-white=40
verde-peak=70 wedding-lily=80 wild-yucca=82""".split())


def technistone_urls(colour, material):
    slug = slugify(re.sub(r"\d+$", "", colour.strip()))
    cid = TECHNISTONE_IDS.get(slug)
    if not cid:
        return []
    return [(f"https://www.technistone.com/cache/color-detail-fullslab/default/_color-{cid}.jpg",
             f"https://www.technistone.com/gbr/color/{slug}")]


_CAESARSTONE_LINKS = None


def _caesarstone_page(colour):
    """Find the colour's real page URL from the catalogue (slugs carry codes/suffixes)."""
    global _CAESARSTONE_LINKS
    if _CAESARSTONE_LINKS is None:
        r = requests.get("https://www.caesarstone.co.uk/catalogue/", timeout=60, headers=UA)
        _CAESARSTONE_LINKS = sorted(set(re.findall(
            r"https://www\.caesarstone\.co\.uk/catalogue/[a-z0-9-]+/", r.text)))
    cn = slugify(re.sub(r"\d+$", "", colour.strip()))
    for link in _CAESARSTONE_LINKS:
        path = link.rstrip("/").rsplit("/", 1)[-1]
        path_name = re.sub(r"^\d+-", "", path)
        if path_name.startswith(cn):
            return link
    return None


def caesarstone_urls(colour, material):
    page = _caesarstone_page(colour)
    if not page:
        return []
    try:
        r = requests.get(page, timeout=30, headers=UA)
        if r.status_code != 200:
            return []
    except Exception:
        return []
    urls = set(re.findall(r"https://www\.caesarstone\.co\.uk/wp-content/uploads/[^\"'\s]+", r.text))
    def area(u):  # prefer the widest master, e.g. "..._3840X1812.webp"
        dims = re.findall(r"(\d{3,4})[xX](\d{3,4})", u.rsplit("/", 1)[-1])
        return max((int(w) * int(h) for w, h in dims), default=0)
    fulls = sorted({re.sub(r"-\d+x\d+(?=\.\w+$)", "", u) for u in urls if "_full_" in u.lower()},
                   key=area, reverse=True)
    posters = {re.sub(r"-\d+x\d+(?=\.\w+$)", "", u) for u in urls if "slab-video-poster" in u.lower()}
    return [(u, r.url) for u in fulls + sorted(posters)]


NEOLITH_PATHS = """fusion/toscano fusion/colosseo fusion/serpeggiante fusion/obsidian colorfeel/nivola
classtone/abu-dhabi-white classtone/everest-sunrise fusion/azahar steel/metropolitan classtone/amazonico
iron/iron-grey timber/summer-dala classtone/arabesque fusion/krater iconic-design/victoria
classtone/calacatta-roma fusion/cappadocia-sunset iron/iron-frost colorfeel/nero fusion/black-obsession
classtone/calacatta-royale classtone/calacatta-c01-c01r timber/la-boheme-b01 fusion/retrostone
fusion/pietra-grey timber/pasadena classtone/calacatta-gold-cg01-cg01r iron/iron-corten
colorfeel/just-white classtone/calista classtone/colorado-dunes classtone/calacatta-luxe-cl01-cl01r
fusion/pietra-di-piombo iron/iron-copper fusion/pietra-di-osso classtone/taj-mahal fusion/pietra-di-luna
classtone/azure colorfeel/lux classtone/niagara classtone/calatorao colorfeel/arctic-white fusion/creme
classtone/estatuario-e01-e01r classtone/san-simone classtone/himalaya-crystal fusion/mamba
fusion/new-york-new-york classtone/layla fusion/nero-zimbabwe classtone/mont-blanc classtone/pulpis
classtone/strata-argentum fusion/cement fusion/beton fusion/basalt-grey fusion/basalt-black fusion/barro
fusion/aspen-grey fusion/arena fusion/zaha-stone classtone/whitesands fusion/wulong fusion/artisan
fusion/rapolano fusion/ignea fusion/terrazo-ceppo fusion/shilin""".split()


def neolith_urls(colour, material):
    cn = slugify(re.sub(r"\d+$", "", colour.strip()))
    path = None
    for p in NEOLITH_PATHS:
        pslug = p.split("/")[1]
        base = re.sub(r"(-[a-z]{1,2}\d{2}[a-z0-9-]*)+$", "", pslug)  # strip code suffixes like -cg01-cg01r
        if pslug == cn or base == cn or pslug.startswith(cn) or cn.startswith(base):
            path = p
            break
    if not path:
        return []
    page = f"https://www.neolith.com/en/collections/{path}/"
    try:
        r = requests.get(page, timeout=30, headers=UA)
        if r.status_code != 200:
            return []
    except Exception:
        return []
    urls = set(re.findall(r"https://a\.storyblok\.com/[^\"'<>\s]+\.(?:jpg|jpeg|png|webp)", r.text))
    slabs = [u for u in urls if "_slab" in u.lower()]
    others = [u for u in urls if "imagen-destacada" in u.lower()]
    return [(u + "/m/1600x0", page) for u in slabs + others]


_RT_CACHE = None


def rtstone_urls(colour, material):
    global _RT_CACHE
    if _RT_CACHE is None:
        _RT_CACHE = []
        for page in ("products", "stock"):
            try:
                r = requests.get(f"https://www.quartzbyrtstone.co.uk/{page}", timeout=30, headers=UA)
                _RT_CACHE += re.findall(r'src="(images/[^"]+\.(?:jpg|jpeg|png|webp))"', r.text, re.I)
            except Exception:
                pass
    cn = norm_str = re.sub(r"[^a-z0-9]+", "", re.sub(r"\d+$", "", colour).lower())
    hits = [u for u in _RT_CACHE
            if cn in re.sub(r"[^a-z0-9]+", "", re.sub(r"^\d+", "", u.rsplit("/", 1)[-1]).lower())]
    hits.sort(key=lambda u: ("full" in u.lower() or "slab" in u.lower()), reverse=True)
    return [("https://www.quartzbyrtstone.co.uk/" + u.replace(" ", "%20"),
             "https://www.quartzbyrtstone.co.uk/products") for u in hits[:3]]


SUPPLIERS = {
    "International Stones (IQ)": iq_urls,
    "Neolith": neolith_urls,
    "RT Stone": rtstone_urls,
    "Picasso Surfaces": wp_media("www.picassostones.com"),
    "B-Stone": wp_media("bstoneuk.co.uk"),
    "Technistone": technistone_urls,
    "Caesarstone": caesarstone_urls,
    "AKG Surfaces": wp_media("akgsurfaces.co.uk"),
    "CRL": wp_media("crlstone.co.uk"),
    "Compac": wp_media("en.compac.es"),
    "Fugen": wp_media("www.fugenstone.co.uk"),
    "Kingstone": wp_media("kingstonequartz.co.uk"),
    "Lumina Stone": wp_media("www.luminastoneuk.com"),
    "Quartz Hub": wp_media("www.quartzhub.co.uk"),
    "UK Stone Company": wp_media("www.ukstonecompany.com"),
    "World Wide Stones": wp_media("www.worldwidestones.co.uk"),
}


def main():
    supplier = sys.argv[1]
    urlgen = SUPPLIERS[supplier]
    db = json.loads(SLABS_JSON.read_text(encoding="utf-8"))
    targets = [s for s in db["slabs"] if s["supplier"] == supplier]
    ok = miss = 0
    misses = []
    for e in targets:
        if e["image"].get("source", "").endswith((".com", ".co.uk")):  # already website-sourced
            ok += 1
            continue
        got = False
        for img_url, prod_url in urlgen(e["colour"], e["material"]):
            try:
                r = requests.get(img_url, timeout=60, headers=UA)
                if r.status_code != 200 or len(r.content) < 5000:
                    continue
                im = Image.open(BytesIO(r.content)).convert("RGB")
                if im.width < 300:
                    continue
                if im.width > MAX_WIDTH:
                    im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
                fname = f"{e['id']}.webp"
                ratio = im.width / im.height if im.height else 0
                # slab-shaped either landscape or portrait (some brands show slabs upright)
                status = "slab" if (1.4 <= ratio <= 3.0 or 0.33 <= ratio <= 0.72) else "closeup-only"
                im.save(IMAGES_DIR / fname, "WEBP", quality=82)
                e["image"] = {"file": fname, "status": status,
                              "source": img_url.split("/")[2].replace("www.", ""), "borrowedFrom": ""}
                e["productUrl"] = prod_url
                ok += 1
                got = True
                break
            except Exception:
                continue
        if not got:
            miss += 1
            misses.append(e["colour"])
        time.sleep(0.25)
    SLABS_JSON.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{supplier}: {ok} have website images, {miss} not found")
    if misses:
        print("Missing:", "; ".join(misses[:40]))


if __name__ == "__main__":
    main()

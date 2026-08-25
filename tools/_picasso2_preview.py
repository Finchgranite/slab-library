"""One-off: download every gallery image from picasso2-harvest.json into
tools/_cache/picasso2/img/, then build small labelled contact sheets (8/row)
for manual kind classification. Not part of the reconcile pipeline -- just
scaffolding to let a human (me) eyeball every image once before hardcoding
the KIND map in reconcile_picasso2.py.
"""
import json
import os
import sys

import harvest_lib as hl

SCRATCH = os.path.dirname(os.path.abspath(__file__))
IMG_CACHE = os.path.join(SCRATCH, "_cache", "picasso2", "img")
os.makedirs(IMG_CACHE, exist_ok=True)

manifest = json.load(open(os.path.join(SCRATCH, "picasso2-harvest.json"), encoding="utf-8"))
colours = manifest["colours"]

entries = []
for rec in colours:
    if rec.get("error"):
        continue
    for i, im in enumerate(rec["images"], 1):
        fn = im["url"].split("/")[-1].split("?")[0]
        local = os.path.join(IMG_CACHE, f"{rec['slug']}__{fn}")
        if not os.path.exists(local) or os.path.getsize(local) == 0:
            try:
                data, used = hl.fetch_best(im["url"], supplier="picasso2",
                                            cache_key=f"dl-{rec['slug']}-{i}")
                open(local, "wb").write(data)
            except Exception as e:
                print(f"FAIL {rec['slug']} #{i}: {e}")
                continue
        entries.append((f"{rec['slug']} #{i}", local))
        print(f"{rec['slug']} #{i} -> {os.path.basename(local)}")

sheets = hl.contact_sheet(entries, os.path.join(SCRATCH, "_cache", "picasso2", "preview_all.png"),
                           cols=6, cell_w=260, cell_h=180)
print("wrote", sheets)

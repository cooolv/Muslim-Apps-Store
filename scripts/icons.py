# يستخرج أيقونة التطبيق (apk) / البرنامج (exe) / الإضافة (zip,crx,xpi) من الملف المرفوع على Releases
import os, io, json, zipfile, requests
from PIL import Image
P = "data/posts.json"
EXT = {"app": (".apk",), "desktop": (".exe",), "addons": (".zip", ".crx", ".xpi")}
NAMES = ("launcher", "ic_app", "app_icon", "icon", "logo")

def apk_icon(path):
    z = zipfile.ZipFile(path)
    try:  # الطريقة الدقيقة: قراءة AndroidManifest (تتعامل مع الأسماء المشفّرة)
        try:
            from loguru import logger; logger.disable("androguard")
        except Exception: pass
        from androguard.core.apk import APK
        n = APK(path).get_app_icon()
        if n and n.lower().endswith((".png", ".webp", ".jpg")):
            return Image.open(io.BytesIO(z.read(n)))
    except Exception: pass
    best, score = None, -1  # بديل: أفضل صورة مربعة اسمها launcher/icon
    for n in z.namelist():
        l = n.lower()
        if not l.startswith("res/") or not l.endswith((".png", ".webp")) or not any(k in l for k in NAMES): continue
        try: im = Image.open(io.BytesIO(z.read(n))); im.load()
        except Exception: continue
        w, h = im.size
        if w != h or w < 48 or w > 1024: continue
        s = 10000 * (not any(k in l for k in ("foreground", "background", "round", "monochrome"))) + w
        if s > score: best, score = im, s
    return best

def exe_icon(path):
    from icoextract import IconExtractor
    IconExtractor(path).export_icon("/tmp/x.ico")
    im = Image.open("/tmp/x.ico"); im.size = max(im.info.get("sizes") or [im.size]); im.load()
    return im

def ext_icon(path):
    z = zipfile.ZipFile(path); names = z.namelist()
    mf = next((n for n in names if n.lower().endswith("manifest.json") and n.count("/") <= 1), None)
    if not mf: return None
    base = mf[:-len("manifest.json")]; m = json.loads(z.read(mf).decode("utf-8-sig")); paths = []
    def add(d):
        if isinstance(d, dict):
            for k, v in d.items():
                try: paths.append((int(k), v))
                except Exception: pass
        elif isinstance(d, str): paths.append((0, d))
    add(m.get("icons"))
    for k in ("action", "browser_action", "page_action"): add((m.get(k) or {}).get("default_icon"))
    for _, v in sorted(paths, key=lambda x: -x[0]):
        n = base + str(v).lstrip("/")
        if n in names:
            try: return Image.open(io.BytesIO(z.read(n)))
            except Exception: continue

def save_png(im, out):
    im = im.convert("RGBA"); w, h = im.size; s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)); im.thumbnail((192, 192))
    if im.size[0] < 32: raise ValueError("الأيقونة صغيرة جداً")
    im.save(out, "PNG")

def main():
    posts = json.load(open(P)); os.makedirs("media", exist_ok=True)
    todo = [p for p in posts if p.get("file") and p.get("type") in EXT and (p.get("doc") or "").lower().endswith(EXT[p["type"]])
            and not p.get("icon") and p.get("itries", 0) < 2][:20]
    print("أيقونات في الانتظار:", len(todo))
    for p in todo:
        path = f"/tmp/ic_{p['id']}"
        try:
            r = requests.get(p["file"], stream=True, timeout=60); r.raise_for_status(); n = 0
            with open(path, "wb") as f:
                for ch in r.iter_content(1 << 20):
                    n += len(ch)
                    if n > 200e6: raise Exception("الملف كبير جداً")
                    f.write(ch)
            im = {"app": apk_icon, "desktop": exe_icon, "addons": ext_icon}[p["type"]](path)
            if im is None: raise Exception("لم توجد أيقونة")
            out = f"media/icon_{p['id']}.png"; save_png(im, out); p["icon"] = out; print("تم:", p["id"])
        except Exception as e:
            p["itries"] = p.get("itries", 0) + 1; print("فشل", p["id"], type(e).__name__, e)
        finally:
            if os.path.exists(path): os.remove(path)
        json.dump(posts, open(P, "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__": main()

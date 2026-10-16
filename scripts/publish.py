# ينشر المنشورات الجديدة على صفحة فيسبوك ومدونة بلوجر. كل المفاتيح من GitHub Secrets فقط.
import os, json, html, requests
P, S, O = "data/posts.json", "data/publish_state.json", "data/overrides.json"
owner, repo = os.environ.get("GITHUB_REPOSITORY", "user/repo").split("/")
SITE = os.environ.get("SITE_URL") or f"https://{owner.lower()}.github.io/{repo}/"
SITE += "" if SITE.endswith("/") else "/"
DRY = bool(os.environ.get("DRY_RUN")); LIMIT = 3  # حد أقصى لعدد المنشورات في كل تشغيل
FB_ID, FB_TOKEN = os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN")
BL_ID = os.environ.get("BLOGGER_BLOG_ID")
BL = [os.environ.get(k) for k in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN")]
LABEL = {"app": "تطبيقات", "desktop": "سطح المكتب", "addons": "إضافات", "media": "ملفات ووسائط", "news": "أخبار"}
EMO = {"app": "📱", "desktop": "🖥", "addons": "🧩", "media": "🎞", "news": "📰"}
G = "https://graph.facebook.com/v21.0/"

def load(f, d):
    try: return json.load(open(f, encoding="utf-8"))
    except Exception: return d
def short(t, n=700):
    t = (t or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"
def parts(p):
    desc = short(p.get("desc", "")) if (p.get("desc") or "").strip() != p["title"].strip() else ""
    if p["type"] != "news" and (p.get("doc") or p.get("file")):
        links = [("⬇️ تحميل من المتجر", f"{SITE}#p{p['id']}"), ("✈️ تحميل من تيليجرام", p["tg"])]
    else:
        links = [("🔗 المنشور الأصلي", p["tg"]), ("🌐 المتجر", SITE)]
    return desc, links
def imgs(p):
    L = [x for x in p.get("images", []) if x.startswith("media/") and os.path.exists(x)]
    if not L and p.get("icon") and os.path.exists(p["icon"]): L = [p["icon"]]
    return L[:4]
def rb(f): return ("p.jpg", open(f, "rb").read())
def chk(r):
    j = r.json()
    if r.status_code >= 400 or "error" in j: raise Exception(str(j)[:300])
    return j

def to_fb(p):
    desc, links = parts(p); d = {"access_token": FB_TOKEN}; ims = imgs(p)
    msg = "\n".join([f"{EMO[p['type']]} {p['title']}", "", desc, ""] + [f"{a}: {b}" for a, b in links] + ["", "#" + LABEL[p["type"]].replace(" ", "_")])
    if not ims: j = chk(requests.post(G + FB_ID + "/feed", data={**d, "message": msg, "link": links[0][1]}, timeout=60))
    elif len(ims) == 1: j = chk(requests.post(G + FB_ID + "/photos", data={**d, "message": msg}, files={"source": rb(ims[0])}, timeout=120))
    else:
        ids = [chk(requests.post(G + FB_ID + "/photos", data={**d, "published": "false"}, files={"source": rb(f)}, timeout=120))["id"] for f in ims]
        data = {**d, "message": msg, **{f"attached_media[{i}]": json.dumps({"media_fbid": x}) for i, x in enumerate(ids)}}
        j = chk(requests.post(G + FB_ID + "/feed", data=data, timeout=60))
    return j.get("post_id") or j.get("id")

def to_blogger(p, tok):
    desc, links = parts(p); e = html.escape
    body = "".join(f'<p><img src="{SITE}{i}" style="max-width:100%;border-radius:12px"></p>' for i in imgs(p))
    body += f"<p>{e(desc).replace(chr(10), '<br>')}</p>" if desc else ""
    body += "".join(f'<p><a href="{e(u)}" style="display:inline-block;padding:10px 22px;background:#0f7a55;color:#fff;border-radius:20px;text-decoration:none">{e(a)}</a></p>' for a, u in links)
    labels = [LABEL[p["type"]]] + ([p["cat"]] if p["type"] == "app" and p.get("cat") else [])
    r = requests.post(f"https://www.googleapis.com/blogger/v3/blogs/{BL_ID}/posts/", headers={"Authorization": "Bearer " + tok},
                      json={"kind": "blogger#post", "title": p["title"], "content": body, "labels": labels}, timeout=60)
    return chk(r).get("url")
def bl_token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data=dict(
        client_id=BL[0], client_secret=BL[1], refresh_token=BL[2], grant_type="refresh_token")).json()
    if "access_token" not in r: raise Exception("oauth: " + str({k: v for k, v in r.items() if "token" not in k})[:200])
    return r["access_token"]

def main():
    fb_on, bl_on = bool(FB_ID and FB_TOKEN), bool(BL_ID and all(BL))
    if not (fb_on or bl_on): print("لا توجد مفاتيح نشر - تخطي"); return
    posts, st = load(P, []), load(S, None)
    if st is None:  # أول تشغيل: لا ننشر القديم أبداً
        st = {"baseline": max([p["id"] for p in posts], default=0), "done": {}, "tries": {}}
        if not DRY: json.dump(st, open(S, "w"), indent=1)
        print("أول تشغيل: لن يُنشر أي منشور قديم. نقطة البداية =", st["baseline"]); return
    ov, tok, n = load(O, {}), None, 0
    for p in sorted(posts, key=lambda p: p["id"]):
        k = str(p["id"]); q = {**p, **ov.get(k, {})}
        if p["id"] <= st["baseline"] or q.get("hidden"): continue
        need = [x for x, on in (("fb", fb_on), ("bl", bl_on)) if on and x not in st["done"].get(k, {}) and st["tries"].get(f"{k}:{x}", 0) < 3]
        if not need: continue
        if n >= LIMIT: break
        n += 1; print("نشر المنشور", k, q["type"], need)
        for x in need:
            if DRY: print(f"[تجربة {x}]", q["title"], parts(q)[1]); continue
            try:
                if x == "fb": ref = to_fb(q)
                else:
                    tok = tok or bl_token(); ref = to_blogger(q, tok)
                st["done"].setdefault(k, {})[x] = ref or True; print("تم", x, ref)
            except Exception as ex:
                st["tries"][f"{k}:{x}"] = st["tries"].get(f"{k}:{x}", 0) + 1; print("فشل", x, type(ex).__name__, str(ex)[:300])
            json.dump(st, open(S, "w"), indent=1)

if __name__ == "__main__": main()

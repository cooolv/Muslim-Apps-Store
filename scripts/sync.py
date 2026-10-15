import re, json, os, requests
from bs4 import BeautifulSoup
CH = os.environ.get("CHANNEL", "muslim_appss")
P = "data/posts.json"
CATS = [("القرآن", r"قرآن|مصحف|تلاوة|تفسير|تجويد"), ("الأذكار", r"أذكار|ذكر|دعاء|أدعية|تسبيح|سبحة"),
        ("الصلاة", r"صلاة|أذان|قبلة|مواقيت"), ("الحديث والفقه", r"حديث|فقه|فتاو|سيرة|بخاري"), ("الأطفال", r"أطفال|طفل|قصص")]
def is_app(text, doc, links):
    if re.search(r"#(خبر|أخبار|اخبار|news)", text, re.I): return False   # وسم صريح: خبر
    if re.search(r"#(تطبيق|تطبيقات|app)", text, re.I): return True       # وسم صريح: تطبيق
    if re.search(r"\.(apk|xapk|apks|obb)$", doc, re.I): return True      # ملف تطبيق
    if any(re.search(r"play\.google|apps\.apple|appgallery|f-droid", l) for l in links): return True
    strong = re.search(r"(apk|رابط التحميل|تحميل التطبيق|حمّل التطبيق|حمل التطبيق|download|الإصدار|النسخة|version)", text, re.I)
    return bool(strong and (links or doc))   # كلمة قوية + رابط أو ملف
def catof(t):
    for n, r in CATS:
        if re.search(r, t): return n
    return "أخرى"
old = json.load(open(P)) if os.path.exists(P) else []
maxknown = max([p["id"] for p in old], default=0)
raw, before = {}, None
for _ in range(300):  # صفحات القناة العامة (بدون أي توكن)
    r = requests.get(f"https://t.me/s/{CH}" + (f"?before={before}" if before else ""), timeout=30)
    ms = BeautifulSoup(r.text, "html.parser").select(".tgme_widget_message")
    if not ms: break
    page = []
    for m in ms:
        try:
            i = int(m["data-post"].split("/")[1])
            t = m.select_one(".tgme_widget_message_text")
            if t:
                for br in t.find_all("br"): br.replace_with("\n")
            photos = []
            for a in m.select(".tgme_widget_message_photo_wrap"):
                u = re.search(r"url\(['\"]?(.+?)['\"]?\)", a.get("style", ""))
                if u: photos.append(u.group(1))
            v = m.select_one("video")
            d = m.select_one(".tgme_widget_message_document_title")
            tm = m.select_one(".tgme_widget_message_date time") or m.select_one("time")
            raw[i] = dict(id=i, date=(tm.get("datetime", "") if tm else ""), text=t.get_text().strip() if t else "",
                          links=[a["href"] for a in t.find_all("a", href=True)] if t else [],
                          photos=photos, video=(v.get("src") or "") if v else "", doc=d.get_text().strip() if d else "")
            page.append(i)
        except Exception as e:
            print("skip message:", e)
    if not page or min(page) <= maxknown + 1: break
    before = min(page)
new, pend = [], []
for i in sorted(raw):
    m = raw[i]
    if i <= maxknown: continue
    if not m["text"]:
        if m["photos"] or m["video"] or m["doc"]: pend.append(m)
        continue
    pend = [x for x in pend if i - x["id"] <= 10]
    for x in pend:
        m["photos"] = x["photos"] + m["photos"]; m["video"] = m["video"] or x["video"]; m["doc"] = m["doc"] or x["doc"]
    pend = []
    lines = [l for l in m["text"].split("\n") if l.strip()]
    ver = re.search(r"(?:v|الإصدار|النسخة|version)\s*[:：]?\s*(\d[\d.]*)", m["text"], re.I)
    app = is_app(m["text"], m["doc"], m["links"])
    imgs = []
    for n, u in enumerate(m["photos"]):
        f = f"media/{i}_{n}.jpg"
        try: open(f, "wb").write(requests.get(u, timeout=30).content); imgs.append(f)
        except Exception: imgs.append(u)
    new.append(dict(id=i, date=m["date"], type="app" if app else "news", title=lines[0][:80],
                    desc="\n".join(lines[1:]) or m["text"], version=ver.group(1) if ver else "",
                    links=[l for l in m["links"] if "t.me" not in l], images=imgs, video=m["video"],
                    doc=m["doc"], cat=catof(m["text"]), tg=f"https://t.me/{CH}/{i}"))
allp = sorted(old + new, key=lambda p: -p["id"])
for p in allp:  # إعادة تصنيف كل المنشورات (القديمة أيضاً) بالقاعدة الجديدة
    p["type"] = "app" if is_app(p["title"] + "\n" + p["desc"], p.get("doc", ""), p.get("links", [])) else "news"
json.dump(allp, open(P, "w"), ensure_ascii=False, indent=1)
print("new posts:", len(new))

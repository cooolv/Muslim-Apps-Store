import re, json, os, requests
from bs4 import BeautifulSoup
CH = os.environ.get("CHANNEL", "muslim_appss")
P = "data/posts.json"
REFRESH = bool(os.environ.get("REFRESH"))  # إعادة فحص كل التاريخ لتحديث بيانات الوسائط
CATS = [("القرآن", r"قرآن|مصحف|تلاوة|تفسير|تجويد"), ("الأذكار", r"أذكار|ذكر|دعاء|أدعية|تسبيح|سبحة"),
        ("الصلاة", r"صلاة|أذان|قبلة|مواقيت"), ("الحديث والفقه", r"حديث|فقه|فتاو|سيرة|بخاري"), ("الأطفال", r"أطفال|طفل|قصص")]
def catof(t):
    for n, r in CATS:
        if re.search(r, t): return n
    return "أخرى"

def ptype(text, doc, video, images, hasmedia):
    """app = ملف apk | desktop = ملف exe | addons = ملف + #اضافه/#اضافات | media = أي وسائط/ملفات أخرى | news = نص فقط"""
    t = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
    ext = os.path.splitext((doc or "").strip().lower())[1]
    if doc and re.search(r"#اضاف(ه|ات)", t): return "addons"
    if ext == ".exe": return "desktop"
    if ext == ".apk": return "app"
    if doc or video or images or hasmedia: return "media"
    return "news"

old = json.load(open(P)) if os.path.exists(P) else []
byid = {p["id"]: p for p in old}
maxknown = max(byid, default=0)
floor = 0 if REFRESH else maxknown
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
            hm = bool(m.select_one(".tgme_widget_message_video_wrap, .tgme_widget_message_roundvideo_wrap, .tgme_widget_message_voice, audio"))
            raw[i] = dict(id=i, date=(tm.get("datetime", "") if tm else ""), text=t.get_text().strip() if t else "",
                          links=[a["href"] for a in t.find_all("a", href=True)] if t else [],
                          photos=photos, video=(v.get("src") or "") if v else "", doc=d.get_text().strip() if d else "", hasmedia=hm or bool(v))
            page.append(i)
        except Exception as e:
            print("skip message:", e)
    if not page or min(page) <= floor + 1: break
    before = min(page)
new, pend = [], []
for i in sorted(raw):
    m = raw[i]
    if i <= maxknown and not REFRESH: continue
    if not m["text"]:
        if m["photos"] or m["video"] or m["doc"] or m["hasmedia"]: pend.append(m)
        continue
    pend = [x for x in pend if i - x["id"] <= 10]
    for x in pend:
        m["photos"] = x["photos"] + m["photos"]; m["video"] = m["video"] or x["video"]
        m["doc"] = m["doc"] or x["doc"]; m["hasmedia"] = m["hasmedia"] or x["hasmedia"]
    pend = []
    if i in byid:  # منشور قديم: نحدّث بيانات الوسائط فقط عند REFRESH
        byid[i]["hasmedia"] = m["hasmedia"]; byid[i]["video"] = byid[i].get("video") or m["video"]
        continue
    lines = [l for l in m["text"].split("\n") if l.strip()]
    ver = re.search(r"(?:v|الإصدار|النسخة|version)\s*[:：]?\s*(\d[\d.]*)", m["text"], re.I)
    imgs = []
    for n, u in enumerate(m["photos"]):
        f = f"media/{i}_{n}.jpg"
        try: open(f, "wb").write(requests.get(u, timeout=30).content); imgs.append(f)
        except Exception: imgs.append(u)
    new.append(dict(id=i, date=m["date"], title=lines[0][:80], desc="\n".join(lines[1:]) or m["text"],
                    version=ver.group(1) if ver else "", links=[l for l in m["links"] if "t.me" not in l],
                    images=imgs, video=m["video"], hasmedia=m["hasmedia"], doc=m["doc"],
                    cat=catof(m["text"]), tg=f"https://t.me/{CH}/{i}"))
allp = sorted(old + new, key=lambda p: -p["id"])
for p in allp:  # تصنيف كل المنشورات (القديمة والجديدة) بنفس القاعدة
    p["type"] = ptype(p["title"] + "\n" + p["desc"], p.get("doc", ""), p.get("video", ""), p.get("images"), p.get("hasmedia", False))
json.dump(allp, open(P, "w"), ensure_ascii=False, indent=1)
print("new posts:", len(new), "| types:", {t: sum(1 for p in allp if p["type"] == t) for t in ("app", "desktop", "addons", "media", "news")})

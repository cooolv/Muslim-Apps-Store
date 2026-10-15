# ينقل ملفات التطبيقات من تيليجرام إلى GitHub Releases ويضيف رابط التحميل المباشر
import os, json, asyncio, subprocess
if not os.environ.get("TG_SESSION"):
    print("TG_SESSION غير مضبوط - تخطي التحميل المباشر"); raise SystemExit
from telethon import TelegramClient
from telethon.sessions import StringSession
CH = os.environ.get("CHANNEL", "muslim_appss"); REPO = os.environ["GITHUB_REPOSITORY"]
posts = json.load(open("data/posts.json"))
todo = [p for p in posts if p.get("doc") and p.get("file") is None][:15]  # دفعة لكل تشغيل

async def main():
    subprocess.run(["gh", "release", "create", "apps", "--title", "apps", "--notes", "app files", "--repo", REPO], capture_output=True)
    async with TelegramClient(StringSession(os.environ["TG_SESSION"]), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as c:
        os.makedirs("/tmp/dl", exist_ok=True)
        for p in todo:
            msgs = await c.get_messages(CH, ids=list(range(p["id"] - 10, p["id"] + 1)))
            m = next((x for x in msgs if x and x.document and x.file and x.file.name == p["doc"]), None)
            if not m or m.file.size > 2_000_000_000: p["file"] = ""; continue
            ext = os.path.splitext(p["doc"])[1] or ".apk"
            path = await c.download_media(m, file=f"/tmp/dl/{p['id']}{ext}")
            r = subprocess.run(["gh", "release", "upload", "apps", path, "--clobber", "--repo", REPO])
            if r.returncode == 0:
                p["file"] = f"https://github.com/{REPO}/releases/download/apps/{p['id']}{ext}"; p["size"] = m.file.size
            os.remove(path)
            json.dump(posts, open("data/posts.json", "w"), ensure_ascii=False, indent=1)
asyncio.run(main())
json.dump(posts, open("data/posts.json", "w"), ensure_ascii=False, indent=1)

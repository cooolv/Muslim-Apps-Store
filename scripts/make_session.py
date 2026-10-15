# شغّله مرة واحدة على جهازك: pip install telethon && python make_session.py
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
i = int(input("api_id: ")); h = input("api_hash: ")
with TelegramClient(StringSession(), i, h) as c:
    print("\nانسخ هذه القيمة كسر TG_SESSION:\n" + c.session.save())

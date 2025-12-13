import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from pymongo import MongoClient

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

NSFW_API = "https://nexacoders-nexa-api.hf.space/scan"

BAD_WORDS = [
    "sex", "porn", "nude", "boobs", "fuck",
    "hentai", "xxx", "slut", "bitch"
]

# ================= DATABASE =================
client = MongoClient(MONGO_URL)
db = client["nsfw_bot"]
groups = db["groups"]

print("✅ MongoDB connected")

# ================= HELPERS =================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id
        )
        return member.status in ("administrator", "creator")
    except:
        return False


def scan_text(text: str) -> bool:
    text_l = text.lower()

    # Fast bad-word check
    for w in BAD_WORDS:
        if w in text_l:
            return True

    # AI scan
    try:
        r = requests.post(
            NSFW_API,
            json={"text": text},
            timeout=10
        )
        data = r.json()
        print("🧠 TEXT API:", data)
        return data.get("nsfw", False)
    except Exception as e:
        print("TEXT API ERROR:", e)
        return False


def scan_image(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            r = requests.post(
                NSFW_API,
                files={"file": f},
                timeout=15
            )
        data = r.json()
        print("🖼 IMAGE API:", data)
        return data.get("nsfw", False)
    except Exception as e:
        print("IMAGE API ERROR:", e)
        return False


# ================= COMMANDS =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡 NSFW Detector Bot\n\n"
        "Admin commands:\n"
        "/nsfw enable\n"
        "/nsfw disable\n"
        "/stats\n\n"
        "Deletes NSFW text, images, GIFs, stickers & videos."
    )


async def nsfw_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return

    if not await is_admin(update, context):
        await update.message.reply_text("❌ Admins only")
        return

    if not context.args:
        await update.message.reply_text("Use: /nsfw enable | disable")
        return

    enable = context.args[0].lower() == "enable"

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": enable}},
        upsert=True
    )

    await update.message.reply_text(
        "✅ NSFW filter enabled" if enable else "❌ NSFW filter disabled"
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    e = groups.count_documents({"enabled": True})
    d = groups.count_documents({"enabled": False})

    await update.message.reply_text(
        f"📊 Stats\n\n"
        f"Enabled groups: {e}\n"
        f"Disabled groups: {d}"
    )


# ================= MESSAGE HANDLER =================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": update.effective_chat.id})
    if not cfg or not cfg.get("enabled"):
        return

    # -------- BLOCK MEDIA TYPES --------
    if msg.sticker or msg.animation or msg.video:
        await msg.delete()
        print("❌ MEDIA DELETED")
        return

    # -------- TEXT --------
    if msg.text or msg.caption:
        text = msg.text or msg.caption
        print("🔎 TEXT:", text)

        if scan_text(text):
            await msg.delete()
            print("❌ NSFW TEXT DELETED")
            return

    # -------- IMAGE --------
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)

        print("🔎 IMAGE SCAN")
        if scan_image(path):
            await msg.delete()
            print("❌ NSFW IMAGE DELETED")


# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("nsfw", nsfw_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.ALL, message_handler))

    print("🤖 NSFW bot running")
    app.run_polling()


if __name__ == "__main__":
    main()
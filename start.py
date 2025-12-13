from telegram import Update
from telegram.ext import ContextTypes

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "👋 **Simple NSFW Detector Bot**\n\n"
            "🛡 Deletes NSFW messages in groups.\n\n"
            "👮 Admin commands:\n"
            "`/nsfw enable`\n"
            "`/nsfw disable`\n\n"
            "➕ Add me to a group and make me admin (delete permission).",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🤖 NSFW Detector Bot\n"
            "Admins can use:\n"
            "`/nsfw enable` | `/nsfw disable`",
            parse_mode="Markdown"
        )
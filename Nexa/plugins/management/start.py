from pyrogram import Client, filters
from pyrogram.types import Message
from Nexa.database.client import get_nsfw_status

# ================= /START =================

@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):

    # ---------- PRIVATE CHAT ----------
    if message.chat.type == "private":
        text = (
            "👋 **Welcome to Nexa NSFW Bot**\n\n"
            "🛡️ I help keep your groups clean by detecting "
            "**porn, hentai, and sexual content** using AI.\n\n"
            "✨ **Features:**\n"
            "• NSFW image & sticker detection\n"
            "• Ultra-fast (Redis + Mongo)\n"
            "• Admin-only controls\n"
            "• Automatic deletion + logs\n\n"
            "⚙️ **Commands:**\n"
            "`/nsfw on` – Enable NSFW filter in group\n"
            "`/nsfw off` – Disable NSFW filter\n\n"
            "➕ **Add me to a group and promote me as admin**\n"
            "(with delete messages permission)\n\n"
            "⚡ Powered by **Nexa**"
        )
        return await message.reply_text(text)

    # ---------- GROUP CHAT ----------
    if message.chat.type in ("group", "supergroup"):
        status = await get_nsfw_status(message.chat.id)
        text = (
            "🤖 **Nexa NSFW Bot is Active**\n\n"
            f"🔞 NSFW Filter: **{'ON' if status else 'OFF'}**\n\n"
            "👮 **Admins only:**\n"
            "`/nsfw on` – Enable filter\n"
            "`/nsfw off` – Disable filter\n\n"
            "⚡ Powered by **Nexa**"
        )
        await message.reply_text(text)
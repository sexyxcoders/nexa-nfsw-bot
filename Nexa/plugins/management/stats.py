from pyrogram import Client, filters
from pyrogram.types import Message

from Nexa.database.client import get_global_stats
from Nexa.utils.decorators import admin_only


# ───────────────── STATS COMMAND ─────────────────

@Client.on_message(filters.command("stats"))
@admin_only
async def stats_handler(client: Client, message: Message):
    """
    Shows global bot statistics
    """

    users, chats = await get_global_stats()

    text = (
        "📊 **Nexa NSFW Bot Stats**\n\n"
        f"👤 **Total Users:** `{users}`\n"
        f"👥 **Total Chats:** `{chats}`\n\n"
        "⚡ Powered by **@NexaCoders**"
    )

    await message.reply_text(text)
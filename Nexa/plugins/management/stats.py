from pyrogram import Client, filters
from pyrogram.types import Message

from Nexa.database.client import get_global_stats


@Client.on_message(filters.command("stats"))
async def nexa_stats(_, message: Message):
    stats = await get_global_stats()

    text = (
        "📊 **Nexa Stats**\n\n"
        f"👥 **Total Users :** `{stats['users']}`\n"
        f"💬 **Chats :** `{stats['chats']}`\n\n"
        "⚡ Powered by **@NexaCoders**"
    )

    await message.reply_text(text)
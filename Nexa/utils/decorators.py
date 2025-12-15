from functools import wraps
from pyrogram.types import Message


def admin_only(func):
    @wraps(func)
    async def wrapper(client, m: Message, *args, **kwargs):

        # ── Must be group or supergroup
        if not m.chat or m.chat.type not in ("group", "supergroup"):
            return await m.reply("❌ This command works only in groups.")

        # ── Ignore messages without users (anonymous / channel)
        if not m.from_user:
            return

        # ── Check admin permissions
        try:
            member = await client.get_chat_member(
                m.chat.id,
                m.from_user.id
            )
        except Exception:
            return await m.reply("❌ Unable to verify admin rights.")

        if member.status not in ("administrator", "creator"):
            return await m.reply("❌ Only group admins can use this.")

        return await func(client, m, *args, **kwargs)

    return wrapper
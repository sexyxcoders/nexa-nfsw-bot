from functools import wraps
from pyrogram.types import Message
from pyrogram.enums import ChatType


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        # ── Ensure group
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply("❌ This command works only in groups.")

        # ── Anonymous admin
        if message.from_user is None:
            return await message.reply("❌ Anonymous admins are not supported.")

        # ── Fetch admins
        try:
            member = await client.get_chat_member(
                message.chat.id,
                message.from_user.id
            )
        except Exception:
            return await message.reply("❌ Failed to verify admin status.")

        # ── Check rights
        if member.status not in ("administrator", "owner"):
            return await message.reply("❌ Only group admins can use this.")

        return await func(client, message, *args, **kwargs)

    return wrapper
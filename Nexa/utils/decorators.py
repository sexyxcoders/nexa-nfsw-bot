from functools import wraps
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        # ── Group check
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply("❌ This command works only in groups.")

        # ── Anonymous admin check
        if message.from_user is None:
            return await message.reply(
                "❌ Anonymous admins are not supported.\n"
                "➡ Disable anonymous admin mode and try again."
            )

        # ── Bot admin check
        try:
            bot_member = await client.get_chat_member(
                message.chat.id,
                "me"
            )
            if bot_member.status not in (
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                return await message.reply(
                    "❌ I must be admin to check permissions."
                )
        except Exception:
            return await message.reply("❌ Failed to verify bot permissions.")

        # ── User admin check
        try:
            user_member = await client.get_chat_member(
                message.chat.id,
                message.from_user.id
            )
        except Exception:
            return await message.reply("❌ Failed to verify admin status.")

        if user_member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return await message.reply("❌ Only group admins can use this.")

        return await func(client, message, *args, **kwargs)

    return wrapper
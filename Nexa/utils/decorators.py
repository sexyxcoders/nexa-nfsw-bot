# Nexa/utils/decorators.py

from functools import wraps
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.types import Message


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        if not message.from_user:
            return

        bot = await client.get_chat_member(message.chat.id, "me")
        if bot.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return

        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return

        return await func(client, message, *args, **kwargs)

    return wrapper


AdminRights = admin_only
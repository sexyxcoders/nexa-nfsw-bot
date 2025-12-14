from functools import wraps
from pyrogram.enums import ChatMemberStatus


def AdminRights(*required_rights):
    """
    Decorator to ensure user has admin rights in group.
    Usage:
        @AdminRights("can_change_info", "can_delete_messages")
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(client, message, *args, **kwargs):
            chat = message.chat
            user = message.from_user

            if not chat or chat.type not in ("supergroup", "group"):
                return

            try:
                member = await client.get_chat_member(chat.id, user.id)
            except Exception:
                return

            # Creator always allowed
            if member.status == ChatMemberStatus.OWNER:
                return await func(client, message, *args, **kwargs)

            # Must be admin
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                await message.reply_text("❌ Admins only.")
                return

            perms = member.privileges
            if not perms:
                await message.reply_text("❌ Insufficient permissions.")
                return

            for right in required_rights:
                if not getattr(perms, right, False):
                    await message.reply_text(f"❌ Missing permission: `{right}`")
                    return

            return await func(client, message, *args, **kwargs)

        return wrapper

    return decorator
import re
from better_profanity import profanity

# Load default + extended bad words
profanity.load_censor_words()

# -----------------------------
# LINK / BIO / PROMOTION REGEX
# -----------------------------
LINK_PATTERN = re.compile(
    r"""
    (https?://)            |   # http / https links
    (www\.)                |   # www links
    (t\.me/)               |   # telegram links
    (@[A-Za-z0-9_]{3,})    |   # @username mentions
    (\.com|\.(net|org|io|in|me)) # common domains
    """,
    re.IGNORECASE | re.VERBOSE
)

# -----------------------------
# BAD WORD CHECK
# -----------------------------
def contains_bad_words(text: str) -> bool:
    """
    Returns True if bad / abusive / NSFW words are found
    """
    if not text:
        return False
    return profanity.contains_profanity(text)


# -----------------------------
# BIO / LINK CHECK
# -----------------------------
def contains_links_or_bio(text: str) -> bool:
    """
    Returns True if links, usernames, or bio-style promotion detected
    """
    if not text:
        return False
    return bool(LINK_PATTERN.search(text))

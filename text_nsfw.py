import requests

# Your HF Space API (recommended instead of hate-speech model)
NSFW_TEXT_API = "https://NexaCoders-nexa-api.hf.space"

BAD_WORDS = [
    "sex", "porn", "nude", "boobs", "fuck",
    "hentai", "xxx", "bitch", "slut"
]

HEADERS = {
    "User-Agent": "Nexa-NSFW-Bot"
}


def is_nsfw_text(text: str) -> bool:
    text = text.lower()

    # -------- FAST KEYWORD CHECK --------
    for word in BAD_WORDS:
        if word in text:
            return True

    # -------- AI API CHECK --------
    try:
        r = requests.post(
            NSFW_TEXT_API,
            json={"text": text},
            headers=HEADERS,
            timeout=10
        )

        data = r.json()
        print("TEXT API RESPONSE:", data)

        # Expected:
        # { "nsfw": true/false }
        if isinstance(data, dict):
            return data.get("nsfw", False)

    except Exception as e:
        print("TEXT NSFW ERROR:", e)

    return False
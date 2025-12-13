import requests

HF_TEXT_API = "https://api-inference.huggingface.co/models/facebook/roberta-hate-speech-dynabench-r4-target"

BAD_WORDS = [
    "sex", "porn", "nude", "boobs", "fuck",
    "hentai", "xxx", "bitch", "slut"
]


def is_nsfw_text(text: str) -> bool:
    t = text.lower()

    # Fast keyword check
    for w in BAD_WORDS:
        if w in t:
            return True

    # AI check
    try:
        r = requests.post(
            HF_TEXT_API,
            json={"inputs": text},
            timeout=8
        )
        data = r.json()
        for item in data[0]:
            if item["score"] > 0.7:
                return True
    except Exception:
        pass

    return False
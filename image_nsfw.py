import requests

NSFW_IMAGE_API = "https://nexacoders-nexa-api.hf.space/scan"

HEADERS = {
    "User-Agent": "Nexa-NSFW-Bot"
}


def is_nsfw_image(image_path: str) -> bool:
    try:
        with open(image_path, "rb") as img:
            r = requests.post(
                NSFW_IMAGE_API,
                files={"file": img},
                headers=HEADERS,
                timeout=15
            )

        data = r.json()
        print("IMAGE API RESPONSE:", data)

        # Case 1: simple response
        if isinstance(data, dict) and "nsfw" in data:
            return data["nsfw"]

        # Case 2: scored labels
        for item in data.get("scores", []):
            if item["label"].lower() in ["porn", "sexy", "hentai"] and item["score"] > 0.6:
                return True

    except Exception as e:
        print("IMAGE NSFW ERROR:", e)

    return False
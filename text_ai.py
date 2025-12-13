from transformers import pipeline

# ------------------------------
# Load AI Text NSFW / Toxic Model
# ------------------------------
# This model detects:
# - sexual content
# - abusive / toxic language
# - harassment
# - explicit text

_classifier = pipeline(
    "text-classification",
    model="unitary/unbiased-toxic-roberta",
    return_all_scores=True
)

# Labels we consider NSFW / unsafe
NSFW_LABELS = {
    "sexual_explicit",
    "toxicity",
    "insult",
    "threat",
    "identity_attack"
}

# Confidence threshold (fixed, no per-group logic)
THRESHOLD = 0.70


def is_nsfw_text(text: str) -> bool:
    """
    Returns True if AI detects NSFW / toxic / sexual text.
    """
    if not text or len(text.strip()) < 3:
        return False

    try:
        # Model max safe length
        result = _classifier(text[:512])[0]
    except Exception:
        return False

    for r in result:
        label = r["label"].lower()
        score = r["score"]

        if label in NSFW_LABELS and score >= THRESHOLD:
            return True

    return False

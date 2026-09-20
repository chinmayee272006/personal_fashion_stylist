"""
Rule-based outfit scoring engine.

Scoring weights (total = 100):
    Body type  : 30 pts
    Skin tone  : 25 pts
    Occasion   : 25 pts
    Colour     : 20 pts
"""

# ── Colour → hex for UI accent tinting ──
COLOUR_HEX = {
    "Black": "#1a1a2e", "White": "#f0f0f0", "Navy": "#1e3a5f",
    "Red": "#dc2626", "Burgundy": "#800020", "Pink": "#ec4899",
    "Green": "#059669", "Olive": "#6b7c3f", "Mustard": "#d4a017",
    "Teal": "#0d9488", "Lavender": "#a78bfa", "Coral": "#f97316",
    "Beige": "#d4b896", "Grey": "#6b7280", "Brown": "#92400e",
    "Blue": "#3b82f6",
}

# ── Group colours for partial-match (harmony) scoring ──
_COLOUR_GROUP = {
    "Black": "neutral", "White": "neutral", "Grey": "neutral", "Beige": "neutral",
    "Red": "warm", "Burgundy": "warm", "Coral": "warm",
    "Mustard": "warm", "Brown": "warm",
    "Navy": "cool", "Blue": "cool", "Teal": "cool", "Green": "cool",
    "Pink": "soft", "Lavender": "soft",
    "Olive": "earthy",
}


def _colour_score(user_colour: str, outfit_colour: str) -> int:
    """Return colour-match points: 20 exact, 10 harmonious, 0 mismatch."""
    if not user_colour or not outfit_colour:
        return 0
    uc, oc = user_colour.strip(), outfit_colour.strip()
    if uc.lower() == oc.lower():
        return 20
    # Neutral outfit colour complements everything
    if _COLOUR_GROUP.get(oc) == "neutral":
        return 10
    # Same colour family
    ug = _COLOUR_GROUP.get(uc)
    og = _COLOUR_GROUP.get(oc)
    if ug and og and ug == og:
        return 10
    return 0


def score_outfit(outfit: dict, profile: dict) -> dict:
    """Score a single outfit against a user profile.

    Parameters
    ----------
    outfit  : dict  — row from the ``outfits`` table
    profile : dict  — row from the ``profiles`` table

    Returns
    -------
    dict  ``{body_type, skin_tone, occasion, colour, total}``
    """
    bd = {"body_type": 0, "skin_tone": 0, "occasion": 0, "colour": 0, "total": 0}

    # Body type  (30 pts)
    if profile.get("body_type") and outfit.get("suitable_body_types"):
        types = [t.strip() for t in outfit["suitable_body_types"].split(",")]
        if profile["body_type"] in types:
            bd["body_type"] = 30

    # Skin tone  (25 pts)
    if profile.get("skin_tone") and outfit.get("suitable_skin_tones"):
        tones = [t.strip() for t in outfit["suitable_skin_tones"].split(",")]
        if profile["skin_tone"] in tones:
            bd["skin_tone"] = 25

    # Occasion   (25 pts)
    if profile.get("occasion") and outfit.get("category"):
        user_occ = [o.strip() for o in profile["occasion"].split(",")]
        if outfit["category"] in user_occ:
            bd["occasion"] = 25

    # Colour     (20 pts)
    bd["colour"] = _colour_score(
        profile.get("favourite_colour", ""),
        outfit.get("colour", ""),
    )

    bd["total"] = bd["body_type"] + bd["skin_tone"] + bd["occasion"] + bd["colour"]
    return bd


def get_recommendations(outfits: list, profile: dict, min_score: int = 1) -> list:
    """Score every outfit, filter by gender and *min_score*, return sorted desc."""
    results = []
    user_gender = profile.get("gender")

    for outfit in outfits:
        gt = outfit.get("gender_target")
        if user_gender and gt and gt != "Unisex" and gt != user_gender:
            continue

        breakdown = score_outfit(outfit, profile)
        if breakdown["total"] >= min_score:
            results.append({"outfit": outfit, "score": breakdown})

    results.sort(key=lambda x: x["score"]["total"], reverse=True)
    return results

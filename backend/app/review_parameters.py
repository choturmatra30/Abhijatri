"""The review form and rating rules, published by the API so the client never hard-codes them.

`GuestReviewCreate` validates against the same constants, so the limits a client reads from
`GET /api/v1/review-parameters` are exactly the limits the server enforces (Review.md 3.1, A2,
6.1 to 6.4).
"""

from app.models import ComfortTier, ReviewCategory, ReviewLanguage, TravellerType

PARAMETERS_VERSION = "2026-10-20"

RATING_MIN = 1
RATING_MAX = 5
DISPLAY_NAME_MAX = 80
TITLE_MIN, TITLE_MAX = 3, 160
NOTE_MIN, NOTE_MAX = 20, 6000

# Review.md 6.1 and 6.4: fixed semester prior and the Top Rated threshold.
COMMUNITY_PRIOR_MEAN = 3.5
COMMUNITY_PRIOR_WEIGHT = 5
COMMUNITY_MIN_REVIEWS = 5

Pair = tuple[str, str]  # (Bangla, English)

CATEGORY_LABELS: dict[ReviewCategory, tuple[Pair, Pair]] = {
    ReviewCategory.CLEANLINESS: (
        ("পরিচ্ছন্নতা", "Cleanliness"),
        ("এলাকা, থাকার জায়গা ও শৌচাগার কতটা পরিষ্কার ছিল?", "How clean were the area, stay and toilets?"),
    ),
    ReviewCategory.ACCESSIBILITY: (
        ("প্রবেশযোগ্যতা", "Accessibility"),
        (
            "শিশু, বয়স্ক বা চলাচলে অসুবিধা আছে এমন মানুষের জন্য যাওয়া কতটা সহজ?",
            "How easy is it for children, older people or people with limited mobility?",
        ),
    ),
    ReviewCategory.HOSPITALITY: (
        ("আতিথেয়তা", "Hospitality"),
        ("স্থানীয় মানুষ ও সেবাদাতাদের আচরণ কেমন ছিল?", "How were you treated by locals and service providers?"),
    ),
    ReviewCategory.FOOD: (
        ("খাবার", "Food"),
        ("খাবারের মান ও বিকল্প কেমন ছিল?", "How good were the food quality and choices?"),
    ),
    ReviewCategory.TRANSPORT: (
        ("যাতায়াত", "Transport"),
        (
            "যাওয়া-আসা ও স্থানীয় যানবাহন কতটা সহজ ও নির্ভরযোগ্য?",
            "How easy and reliable were getting there and getting around?",
        ),
    ),
    ReviewCategory.SAFETY_PERCEPTION: (
        ("নিরাপত্তার অনুভূতি", "Feeling of safety"),
        ("সেখানে আপনি কতটা নিরাপদ বোধ করেছেন?", "How safe did you feel there?"),
    ),
    ReviewCategory.VALUE: (
        ("খরচের মূল্য", "Value for money"),
        ("খরচের তুলনায় অভিজ্ঞতা কেমন ছিল?", "Was the experience worth what you paid?"),
    ),
}

TRAVELLER_LABELS: dict[TravellerType, Pair] = {
    TravellerType.SOLO: ("একা", "Solo"),
    TravellerType.STUDENT: ("শিক্ষার্থী", "Student"),
    TravellerType.COUPLE: ("দম্পতি", "Couple"),
    TravellerType.FAMILY: ("পরিবার", "Family"),
    TravellerType.GROUP: ("দল", "Group"),
}

COMFORT_LABELS: dict[ComfortTier, Pair] = {
    ComfortTier.ECONOMY: ("সাশ্রয়ী", "Economy"),
    ComfortTier.STANDARD: ("স্ট্যান্ডার্ড", "Standard"),
    ComfortTier.PREMIUM: ("প্রিমিয়াম", "Premium"),
}

LANGUAGE_LABELS: dict[ReviewLanguage, Pair] = {
    ReviewLanguage.BN: ("বাংলা", "Bangla"),
    ReviewLanguage.EN: ("ইংরেজি", "English"),
    ReviewLanguage.MIXED: ("বাংলা-ইংরেজি মিশ্র", "Mixed Bangla and English"),
}


def community_score(rating_sum: int, rating_count: int) -> float | None:
    """Bayesian Community Rating (Review.md 6.1); ``None`` until the 6.4 threshold is reached."""
    if rating_count < COMMUNITY_MIN_REVIEWS:
        return None
    return (rating_sum + COMMUNITY_PRIOR_WEIGHT * COMMUNITY_PRIOR_MEAN) / (
        rating_count + COMMUNITY_PRIOR_WEIGHT
    )

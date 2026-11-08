"""Bangladesh's 64 districts and their 8 divisions (sign-up form Step 2; Find People shows the division only)."""

DIVISIONS: dict[str, tuple[str, ...]] = {
    "Barishal": ("Barguna", "Barishal", "Bhola", "Jhalokati", "Patuakhali", "Pirojpur"),
    "Chattogram": (
        "Bandarban", "Brahmanbaria", "Chandpur", "Chattogram", "Cox's Bazar", "Cumilla", "Feni", "Khagrachhari",
        "Lakshmipur", "Noakhali", "Rangamati",
    ),
    "Dhaka": (
        "Dhaka", "Faridpur", "Gazipur", "Gopalganj", "Kishoreganj", "Madaripur", "Manikganj", "Munshiganj",
        "Narayanganj", "Narsingdi", "Rajbari", "Shariatpur", "Tangail",
    ),
    "Khulna": ("Bagerhat", "Chuadanga", "Jashore", "Jhenaidah", "Khulna", "Kushtia", "Magura", "Meherpur", "Narail", "Satkhira"),
    "Mymensingh": ("Jamalpur", "Mymensingh", "Netrokona", "Sherpur"),
    "Rajshahi": ("Bogura", "Chapai Nawabganj", "Joypurhat", "Naogaon", "Natore", "Pabna", "Rajshahi", "Sirajganj"),
    "Rangpur": ("Dinajpur", "Gaibandha", "Kurigram", "Lalmonirhat", "Nilphamari", "Panchagarh", "Rangpur", "Thakurgaon"),
    "Sylhet": ("Habiganj", "Moulvibazar", "Sunamganj", "Sylhet"),
}

DISTRICT_TO_DIVISION: dict[str, str] = {district: division for division, districts in DIVISIONS.items() for district in districts}
DISTRICTS: tuple[str, ...] = tuple(sorted(DISTRICT_TO_DIVISION))

assert len(DISTRICTS) == 64, len(DISTRICTS)


def division_of(district: str | None) -> str | None:
    return DISTRICT_TO_DIVISION.get(district or "")

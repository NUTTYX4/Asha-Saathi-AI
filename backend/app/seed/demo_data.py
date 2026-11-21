"""The synthetic demo dataset: 2 territories, 12 households, 50 people, 4 accounts.

ALL DATA IS SYNTHETIC. Names are invented; there are no phone numbers or identity numbers.
Map pins are placed in public open space inside Cubbon Park, Bengaluru, and do NOT identify
real residences or families. Pin checks: `python -m scripts.verify_demo_pins` (OpenStreetMap).

Ages: adults carry a recorded age (DOB unknown, as is common); children carry a date of birth.
Both are relative to DEMO_AS_OF so a newborn is still a newborn whenever the demo is replayed.
Pregnancy / postnatal / newborn status is an explicit programme enrolment, never inferred.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

DEMO_AS_OF = date(2026, 11, 21)
# Fixed namespace: the same public ID always maps to the same UUID (deterministic seed).
DEMO_NAMESPACE = uuid.UUID("6f1c2a52-9a7e-4e44-9d6b-3c1f4f0b9a10")
SURVEY_VERSION = "demo-v1"
PIN_LANDMARK = "Synthetic demo pin in Cubbon Park public open space - not a real residence"

TERRITORIES = [
    ("DEMO-A", "Demo Territory A (synthetic, Cubbon Park north)"),
    ("DEMO-B", "Demo Territory B (synthetic, Cubbon Park south)"),
]

# username, display name, role, territory codes
ACCOUNTS = [
    ("demo_worker_a", "Demo ASHA Worker A", "worker", ["DEMO-A"]),
    ("demo_worker_b", "Demo ASHA Worker B", "worker", ["DEMO-B"]),
    ("demo_supervisor", "Demo Supervisor", "supervisor", ["DEMO-A", "DEMO-B"]),
    ("demo_admin", "Demo Admin", "admin", []),
]

# Pins chosen from OpenStreetMap data (Cubbon Park = OSM way 22895320, OSM base 2026-11-21):
# inside the park boundary, >= 35 m from any mapped building, >= 20 m from motor roads,
# >= 80 m apart from each other. (latitude, longitude), WGS84.
PINS = {
    "H-001": (12.978189, 77.594572),
    "H-002": (12.977827, 77.593926),
    "H-003": (12.977466, 77.594572),
    "H-004": (12.977104, 77.593926),
    "H-005": (12.977104, 77.595217),
    "H-006": (12.976742, 77.594572),
    "H-007": (12.971857, 77.590792),
    "H-008": (12.971495, 77.590147),
    "H-009": (12.971495, 77.591437),
    "H-010": (12.971133, 77.590792),
    "H-011": (12.970771, 77.590147),
    "H-012": (12.970319, 77.590792),
}
MIN_PIN_SEPARATION_M = 75  # checked in the database (allows for coordinate rounding)


@dataclass(frozen=True)
class Member:
    key: str                      # local key within the household
    name: str
    sex: str
    rel_to_head: str
    age_years: int | None = None  # recorded age (adults)
    dob_days_ago: int | None = None  # date of birth = DEMO_AS_OF - days (children)


@dataclass(frozen=True)
class HouseholdSpec:
    public_id: str
    territory: str
    label: str
    scenario: str                 # documentation only; not stored (not a clinical label)
    members: list[Member]
    relationships: list[tuple[str, str, str]] = field(default_factory=list)  # (from, type, to)
    enrolments: list[tuple[str, str, int]] = field(default_factory=list)     # (member, programme, started_days_ago)
    water: str = "piped"
    toilet: bool | None = True


def _y(years: int, extra_days: int = 0) -> int:
    return years * 365 + extra_days


HOUSEHOLDS: list[HouseholdSpec] = [
    HouseholdSpec("H-001", "DEMO-A", "Demo House 1, Synthetic Lane A", "Routine adult household", [
        Member("a", "Ramesh Hosamane", "male", "head", age_years=46),
        Member("b", "Lakshmi Hosamane", "female", "spouse", age_years=41),
        Member("c", "Kiran Hosamane", "male", "son", age_years=19),
        Member("d", "Pooja Hosamane", "female", "daughter", dob_days_ago=_y(16, 40)),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("b", "mother_of", "d"),
        ("a", "father_of", "c"), ("a", "father_of", "d")]),
    HouseholdSpec("H-002", "DEMO-A", "Demo House 2, Synthetic Lane A", "Older adult follow-up", [
        Member("a", "Shivappa Kerekatte", "male", "head", age_years=72),
        Member("b", "Gowramma Kerekatte", "female", "spouse", age_years=67),
        Member("c", "Manjunath Kerekatte", "male", "son", age_years=44),
        Member("d", "Savitha Kerekatte", "female", "daughter_in_law", age_years=39),
        Member("e", "Rahul Kerekatte", "male", "grandson", dob_days_ago=_y(12, 100)),
    ], [("a", "spouse_of", "b"), ("a", "father_of", "c"), ("b", "mother_of", "c"),
        ("c", "spouse_of", "d"), ("c", "father_of", "e"), ("d", "mother_of", "e")],
        enrolments=[("a", "NCD_FOLLOWUP", 400)], water="public_tap"),
    HouseholdSpec("H-003", "DEMO-A", "Demo House 3, Synthetic Lane A", "Mother + newborn linked as two people", [
        Member("a", "Prakash Halli", "male", "head", age_years=30),
        Member("b", "Kavya Halli", "female", "spouse", age_years=26),
        Member("c", "Baby of Kavya Halli", "male", "son", dob_days_ago=6),
        Member("d", "Nagamma Halli", "female", "mother", age_years=55),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("a", "father_of", "c"), ("d", "mother_of", "a")],
        enrolments=[("b", "PNC", 6), ("c", "NEWBORN", 6)]),
    HouseholdSpec("H-004", "DEMO-A", "Demo House 4, Synthetic Lane A", "School-age child household", [
        Member("a", "Suresh Doddamane", "male", "head", age_years=38),
        Member("b", "Rekha Doddamane", "female", "spouse", age_years=34),
        Member("c", "Ananya Doddamane", "female", "daughter", dob_days_ago=_y(9, 150)),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("a", "father_of", "c")], water="tube_well"),
    HouseholdSpec("H-005", "DEMO-A", "Demo House 5, Synthetic Lane A", "Explicitly registered ANC beneficiary", [
        Member("a", "Naveen Kallur", "male", "head", age_years=29),
        Member("b", "Divya Kallur", "female", "spouse", age_years=24),
        Member("c", "Basavaraj Kallur", "male", "father", age_years=60),
        Member("d", "Shantamma Kallur", "female", "mother", age_years=54),
    ], [("a", "spouse_of", "b"), ("c", "spouse_of", "d"), ("c", "father_of", "a"), ("d", "mother_of", "a")],
        enrolments=[("b", "ANC", 120)]),
    HouseholdSpec("H-006", "DEMO-A", "Demo House 6, Synthetic Lane A", "Immunisation follow-up", [
        Member("a", "Girish Hebbar", "male", "head", age_years=33),
        Member("b", "Sowmya Hebbar", "female", "spouse", age_years=29),
        Member("c", "Aarav Hebbar", "male", "son", dob_days_ago=_y(2, 30)),
        Member("d", "Diya Hebbar", "female", "daughter", dob_days_ago=270),
        Member("e", "Kamala Hebbar", "female", "mother", age_years=58),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("b", "mother_of", "d"),
        ("a", "father_of", "c"), ("a", "father_of", "d"), ("e", "mother_of", "a")],
        enrolments=[("c", "IMMUNISATION", _y(2, 30)), ("d", "IMMUNISATION", 270)],
        water="public_tap", toilet=False),
    HouseholdSpec("H-007", "DEMO-B", "Demo House 7, Synthetic Lane B", "PNC follow-up", [
        Member("a", "Harish Gowda", "male", "head", age_years=31),
        Member("b", "Meghana Gowda", "female", "spouse", age_years=27),
        Member("c", "Baby of Meghana Gowda", "male", "son", dob_days_ago=20),
        Member("d", "Tanvi Gowda", "female", "daughter", dob_days_ago=_y(4, 60)),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("b", "mother_of", "d"),
        ("a", "father_of", "c"), ("a", "father_of", "d")],
        enrolments=[("b", "PNC", 20), ("c", "NEWBORN", 20)]),
    HouseholdSpec("H-008", "DEMO-B", "Demo House 8, Synthetic Lane B", "Older adult household", [
        Member("a", "Sharadamma Patil", "female", "head", age_years=70),
        Member("b", "Mahesh Patil", "male", "son", age_years=46),
        Member("c", "Vani Patil", "female", "daughter_in_law", age_years=42),
        Member("d", "Nikhil Patil", "male", "grandson", dob_days_ago=_y(17, 200)),
    ], [("a", "mother_of", "b"), ("b", "spouse_of", "c"), ("b", "father_of", "d"), ("c", "mother_of", "d")],
        water="tanker"),
    HouseholdSpec("H-009", "DEMO-B", "Demo House 9, Synthetic Lane B", "Synthetic newborn referral scenario", [
        Member("a", "Vinay Naik", "male", "head", age_years=28),
        Member("b", "Bhavya Naik", "female", "spouse", age_years=23),
        Member("c", "Baby of Bhavya Naik", "female", "daughter", dob_days_ago=4),
        Member("d", "Ramappa Naik", "male", "father", age_years=57),
        Member("e", "Yashoda Naik", "female", "mother", age_years=52),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("a", "father_of", "c"),
        ("d", "spouse_of", "e"), ("d", "father_of", "a"), ("e", "mother_of", "a")],
        enrolments=[("b", "PNC", 4), ("c", "NEWBORN", 4)], water="public_tap"),
    HouseholdSpec("H-010", "DEMO-B", "Demo House 10, Synthetic Lane B", "Missed routine follow-up", [
        Member("a", "Dinesh Shetty", "male", "head", age_years=40),
        Member("b", "Shobha Shetty", "female", "spouse", age_years=36),
        Member("c", "Sneha Shetty", "female", "daughter", dob_days_ago=_y(13, 80)),
        Member("d", "Varun Shetty", "male", "son", dob_days_ago=_y(10, 210)),
    ], [("a", "spouse_of", "b"), ("b", "mother_of", "c"), ("b", "mother_of", "d"),
        ("a", "father_of", "c"), ("a", "father_of", "d")]),
    HouseholdSpec("H-011", "DEMO-B", "Demo House 11, Synthetic Lane B", "General household visit", [
        Member("a", "Venkatesh Bhat", "male", "head", age_years=50),
        Member("b", "Usha Bhat", "female", "spouse", age_years=47),
        Member("c", "Arjun Bhat", "male", "son", age_years=24),
        Member("d", "Nisha Bhat", "female", "daughter_in_law", age_years=22),
    ], [("a", "spouse_of", "b"), ("a", "father_of", "c"), ("b", "mother_of", "c"), ("c", "spouse_of", "d")]),
    HouseholdSpec("H-012", "DEMO-B", "Demo House 12, Synthetic Lane B", "Routine adult household", [
        Member("a", "Deepa Rao", "female", "head", age_years=36),
        Member("b", "Saroja Rao", "female", "mother", age_years=61),
        Member("c", "Rohan Rao", "male", "son", dob_days_ago=_y(14, 20)),
        Member("d", "Ishita Rao", "female", "daughter", dob_days_ago=_y(11, 300)),
    ], [("b", "mother_of", "a"), ("a", "mother_of", "c"), ("a", "mother_of", "d")], water="tube_well"),
]


def person_public_ids() -> dict[tuple[str, str], str]:
    """(household public_id, member key) -> P-### in dataset order (P-001 .. P-050)."""
    ids, n = {}, 0
    for hh in HOUSEHOLDS:
        for m in hh.members:
            n += 1
            ids[(hh.public_id, m.key)] = f"P-{n:03d}"
    return ids


def stable_uuid(public_key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, public_key)


EXPECTED_MEMBER_COUNTS = {hh.public_id: len(hh.members) for hh in HOUSEHOLDS}
EXPECTED_HOUSEHOLDS = len(HOUSEHOLDS)          # 12
EXPECTED_PEOPLE = sum(EXPECTED_MEMBER_COUNTS.values())  # 50

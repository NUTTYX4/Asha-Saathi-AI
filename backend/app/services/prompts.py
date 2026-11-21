"""Fixed agent utterances (Kannada). PENDING native-speaker review.

No utterance may diagnose, prescribe or give dosage advice.
Numbers are written as words because Timbre expects spoken-form numbers.
"""

from app.schemas.visit import VisitRecord, VisitType
from app.services.numbers import digits_to_kannada, to_kannada_words

DISCLOSURE = (
    "ನಮಸ್ಕಾರ! ನಾನು ಆಶಾ ಸಾಥಿ, ಒಂದು AI ಸಹಾಯಕ. ನಾನು ಮನುಷ್ಯರಲ್ಲ. "
    "ಮನೆ ಭೇಟಿಯ ವಿವರಗಳನ್ನು ಹೇಳಿ."
)

ASK_FIELD = {
    "beneficiary_id": "ಫಲಾನುಭವಿ ಐಡಿ ಹೇಳಿ.",
    "visit_type": "ಇದು ANC, PNC, ನವಜಾತ ಶಿಶು, ಅಥವಾ ಲಸಿಕೆ ಭೇಟಿಯೇ?",
    "next_visit_date": "ಮುಂದಿನ ಭೇಟಿಯ ದಿನಾಂಕ ಯಾವಾಗ?",
}

ASK_WHAT_TO_CHANGE = "ಯಾವುದನ್ನು ಬದಲಾಯಿಸಬೇಕು? ಉದಾಹರಣೆಗೆ, ತೂಕ ಎರಡು ಪಾಯಿಂಟ್ ಎಂಟು ಕಿಲೋ."
NOT_UNDERSTOOD_CONFIRM = "ಅರ್ಥವಾಗಲಿಲ್ಲ. ಸರಿ ಇದ್ದರೆ ಹೌದು ಎನ್ನಿ, ಇಲ್ಲದಿದ್ದರೆ ತಿದ್ದುಪಡಿ ಹೇಳಿ."
RECORD_CHANGED = "ದಾಖಲೆ ಬದಲಾಗಿದೆ. ಮತ್ತೆ ಓದುತ್ತೇನೆ."
SAVED = "ದಾಖಲೆ ಉಳಿಸಲಾಗಿದೆ. ಧನ್ಯವಾದಗಳು. ಮುಂದಿನ ಭೇಟಿಯ ವಿವರ ಹೇಳಬಹುದು."

MONTHS_KN = [
    "", "ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್",
    "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್",
]


# Short spoken names; the screen shows the full labels.
VISIT_TYPE_SHORT_KN = {
    VisitType.ANC: "ANC",
    VisitType.PNC: "PNC",
    VisitType.NEWBORN: "ನವಜಾತ ಶಿಶು",
    VisitType.IMMUNISATION: "ಲಸಿಕೆ ಭೇಟಿ",
    VisitType.UNKNOWN: "ಭೇಟಿ ತಿಳಿದಿಲ್ಲ",
}

CONFIRM_QUESTION = "ಸರಿಯೇ? ಹೌದು ಎನ್ನಿ, ಅಥವಾ ತಿದ್ದುಪಡಿ ಹೇಳಿ."


def _field_phrase(record: VisitRecord, name: str) -> str | None:
    """Spoken phrase for one captured field, or None if it was not mentioned."""
    if name == "beneficiary_id" and record.beneficiary_id:
        return f"ಐಡಿ {digits_to_kannada(record.beneficiary_id)}"
    if name == "visit_type":
        return VISIT_TYPE_SHORT_KN[record.visit_type]
    if name == "weight_kg" and record.weight_kg is not None:
        return f"ತೂಕ {to_kannada_words(record.weight_kg)} ಕಿಲೋ"
    if name == "vaccinations_due" and record.vaccinations_due is not None:
        return f"ಲಸಿಕೆ {', '.join(record.vaccinations_due)}" if record.vaccinations_due else "ಲಸಿಕೆ ಬಾಕಿ ಇಲ್ಲ"
    if name == "next_visit_date" and record.next_visit_date:
        d = record.next_visit_date
        return f"ಮುಂದಿನ ಭೇಟಿ {MONTHS_KN[d.month]} {to_kannada_words(d.day)}"
    return None


READBACK_ORDER = ("beneficiary_id", "visit_type", "weight_kg", "vaccinations_due", "next_visit_date")


def readback(record: VisitRecord, danger_labels: list[str]) -> str:
    """Compact full read-back: every captured field, then explicit confirmation."""
    phrases = [p for name in READBACK_ORDER if (p := _field_phrase(record, name))]
    text = ", ".join(phrases) + "."
    if danger_labels:
        text += f" ಅಪಾಯ: {', '.join(danger_labels)}, PHC ರೆಫರ್."
    return f"{text} {CONFIRM_QUESTION}"


def readback_changes(record: VisitRecord, changed: list[str]) -> str:
    """After a correction: read only the changed fields; the rest was already read."""
    phrases = [p for name in READBACK_ORDER if name in changed and (p := _field_phrase(record, name))]
    return f"{', '.join(phrases)}. ಉಳಿದದ್ದು ಹಾಗೆಯೇ. {CONFIRM_QUESTION}"

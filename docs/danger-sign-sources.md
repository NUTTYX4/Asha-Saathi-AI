# Danger-sign rule sources

ASHA SAATHI AI flags only the danger signs listed in `backend/app/safety/rules.json`. A match produces
a fixed instruction to refer to the PHC now. It never diagnoses, prescribes, or gives dosage advice.

## Source

**World Health Organization, UNFPA, UNICEF. *Pregnancy, childbirth, postpartum and newborn care: A guide
for essential practice*, 3rd edition. Geneva: WHO; 2015 (published 29 January 2015). 184 pp.
ISBN 978 92 4 154935 6.** <https://www.who.int/publications/i/item/9789241549356>

**Status:**
- **Verified on 21 Nov 2026** from the WHO publication page: the title, edition, publication date, editors,
  ISBN and page count.
- **Not verified: the section and page reference for each rule below.** The PDF is hosted on
  iris.who.int, which refused automated access (HTTP 403), so no page numbers are recorded here. Do not
  add any until someone has read them in the document.
- **Owner:** Member 2 (research and QA). Open the PDF linked from the WHO page and record the section code
  and printed page for each sign. Also record any rule to add, remove or reword.

| Rule ID | Population | Sign |
| --- | --- | --- |
| MAT_VAGINAL_BLEEDING | Pregnancy / postpartum | Vaginal bleeding |
| MAT_CONVULSIONS | Pregnancy / postpartum | Convulsions |
| MAT_SEVERE_HEADACHE_BLURRED_VISION | Pregnancy / postpartum | Severe headache or blurred vision |
| MAT_HIGH_FEVER | Pregnancy / postpartum | High fever |
| MAT_SEVERE_ABDOMINAL_PAIN | Pregnancy / postpartum | Severe abdominal pain |
| MAT_DIFFICULT_BREATHING | Pregnancy / postpartum | Fast or difficult breathing |
| NB_NOT_FEEDING | Newborn | Not feeding well |
| NB_CONVULSIONS | Newborn | Convulsions |
| NB_FAST_BREATHING_CHEST_INDRAWING | Newborn | Fast breathing or chest indrawing |
| NB_FEVER | Newborn | Fever |
| NB_TOO_COLD | Newborn | Too cold to touch |
| NB_NO_MOVEMENT | Newborn | No movement / lethargic |
| NB_YELLOW_PALMS_SOLES | Newborn | Yellow palms or soles |

## Matching behaviour

- **Deterministic:** keyword matching in Kannada and English (`backend/app/safety/danger_signs.py`). No
  LLM decides whether to escalate.
- **Negation:** explicit negation is not flagged ("no fever", "ಜ್ವರ ಇಲ್ಲ"). Anything else that mentions a
  listed sign is flagged, because a missed sign is worse than an extra referral prompt.
- **Patient scoping.**
  - **Visit type:** ANC checks the maternal rules. Newborn and immunisation visits check the newborn rules.
    PNC or an unknown visit type checks both. A visit type named in the same sentence counts immediately ("ನವಜಾತ ಶಿಶು
    ಭೇಟಿ, ಮಗುವಿಗೆ ಜ್ವರ" flags only `NB_FEVER`).
  - **Subject words:** words like ಮಗು/baby or ತಾಯಿ/mother only choose between a maternal and a newborn rule
    triggered by the same phrase (for example fever). A sign that has a rule for only one population, such
    as bleeding, is never dropped.
  - **Unclear patient:** if it is still unclear who the sign belongs to, both rules stay flagged. The alert
    repeats the worker's own words and does not name a patient category.
  - **Rescoping:** when the visit type becomes known later, only the wrong-population duplicate is
    removed. A referral is never removed outright.
- **Pending review:** the Kannada keyword lists need native-speaker review.

"""Monitoring alert rules. Transparent rules only: no ML and no Django, so a reviewer can read them.

DRAFT: thresholds need clinical review before any use. Real IBDMDB data gave no predictive signal for
next-visit disease activity (AUC 0.45), so these alerts flag recorded changes and never predict a flare.
Changing any rule must bump RULES_VERSION.
"""
from dataclasses import dataclass

RULES_VERSION = "alerts-draft-1"

CALPROTECTIN_CUTOFF = 150.0   # µg/g
CRP_CUTOFF = 5.0              # mg/L
PROBABILITY_RISE = 0.15       # 15 percentage points

TIER_ORDER = {"Low": 0, "Moderate": 1, "High": 2}

# Appendectomy and tonsillectomy are history items, not red flags; appendectomy is also never narrated.
RED_FLAGS = {
    "perianal_fistula_history": "Perianal fistula / abscess",
    "recurrent_aphthous_ulcers": "Recurrent mouth ulcers",
    "erythema_nodosum_history": "Erythema nodosum",
    "pyoderma_gangrenosum_history": "Pyoderma gangrenosum",
    "hidradenitis_suppurativa_history": "Hidradenitis suppurativa",
    "PSC_or_elevated_LFTs": "PSC / elevated liver enzymes",
    "unprovoked_VTE_history": "Unprovoked VTE",
}

SOURCE_PRODUCT = "AIGUT product rule on the prototype estimate; not a clinical guideline."
SOURCE_CALPROTECTIN = ("AGA 2023 biomarker guidelines use 150 µg/g (Crohn's: Gastroenterology 2023;165:1367-1399; "
                       "UC: Singh et al. 2023). Checked from abstracts and summaries; confirm against the full text.")
SOURCE_CRP = ("Research library: Diagnostic Accuracy of Noninvasive Biomarkers and Imaging for Evaluating "
              "Postoperative Recurrence in Crohn's Disease (2025), which uses CRP 5.0 mg/L.")
SOURCE_RED_FLAG = ("Research library: Munster et al., Techniques in Coloproctology 2025 (perianal red flags); "
                   "extra-intestinal manifestations per the Detailed Project Report.")

# Shown on the About page so a clinician can review and sign off every rule.
RULE_TABLE = [
    ("tier_up", "Risk tier moves up (Low to Moderate, or to High)", SOURCE_PRODUCT),
    ("probability_rise", f"Estimate rises by at least {PROBABILITY_RISE:.0%} points", SOURCE_PRODUCT),
    ("calprotectin_cross", f"Calprotectin rises above {CALPROTECTIN_CUTOFF:g} µg/g", SOURCE_CALPROTECTIN),
    ("crp_cross", f"CRP rises above {CRP_CUTOFF:g} mg/L", SOURCE_CRP),
    ("new_red_flag", "A red flag is newly recorded", SOURCE_RED_FLAG),
]


@dataclass(frozen=True)
class AlertSpec:
    rule_id: str
    severity: str  # "urgent" or "review"
    title: str
    detail: str
    source: str


def headline(care_status):
    """'Flare' only applies to diagnosed IBD; a person without IBD can only show possible progression."""
    return "Possible flare" if care_status == "diagnosed" else "Possible progression"


def _number(inputs, key):
    try:
        return float(inputs.get(key))
    except (TypeError, ValueError):
        return None


def _present(value):
    return value in (1, 1.0, "1", "1.0", "Yes")


def _crossed(before, now, cutoff):
    return before is not None and now is not None and before <= cutoff < now


def evaluate(care_status, current, previous):
    """Compare two saved assessments (objects with .probability, .tier and .inputs); return AlertSpecs."""
    if previous is None:
        return []
    head = headline(care_status)
    out = []

    now_tier, was_tier = TIER_ORDER.get(current.tier, 0), TIER_ORDER.get(previous.tier, 0)
    if now_tier > was_tier:
        out.append(AlertSpec(
            "tier_up", "urgent" if current.tier == "High" else "review",
            f"{head}: risk level rose to {current.tier}",
            f"Estimated risk level moved from {previous.tier} to {current.tier}.", SOURCE_PRODUCT))

    if round(current.probability - previous.probability, 6) >= PROBABILITY_RISE:
        out.append(AlertSpec(
            "probability_rise", "review", f"{head}: estimated risk increased",
            f"Estimate rose from {previous.probability:.0%} to {current.probability:.0%}.", SOURCE_PRODUCT))

    before, now = _number(previous.inputs, "fecal_calprotectin_ug_g"), _number(current.inputs, "fecal_calprotectin_ug_g")
    if _crossed(before, now, CALPROTECTIN_CUTOFF):
        out.append(AlertSpec(
            "calprotectin_cross", "review", f"{head}: calprotectin above {CALPROTECTIN_CUTOFF:g} µg/g",
            f"Fecal calprotectin rose from {before:g} to {now:g} µg/g.", SOURCE_CALPROTECTIN))

    before, now = _number(previous.inputs, "CRP_mg_L"), _number(current.inputs, "CRP_mg_L")
    if _crossed(before, now, CRP_CUTOFF):
        out.append(AlertSpec(
            "crp_cross", "review", f"{head}: CRP above {CRP_CUTOFF:g} mg/L",
            f"CRP rose from {before:g} to {now:g} mg/L.", SOURCE_CRP))

    new_flags = [label for key, label in RED_FLAGS.items()
                 if _present(current.inputs.get(key)) and not _present(previous.inputs.get(key))]
    if new_flags:
        out.append(AlertSpec(
            "new_red_flag", "urgent", f"{head}: new red flag recorded",
            "Newly recorded: " + ", ".join(new_flags) + ".", SOURCE_RED_FLAG))
    return out

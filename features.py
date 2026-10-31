"""Feature definitions, encodings and governance rules for the IBD risk model.

All rules follow the README sheet of Saudi_IBD_Synthetic.xlsx (governance review 2026-10-07).
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "Saudi_IBD_Synthetic.xlsx"
SHEET = "Synthetic_Data"
TARGET = "synthetic_IBD_outcome"

# Never used as features (README §6-7): id + targets/leakage, the 3 composites (Option A),
# and oral_contraceptive_use (sex-specific, README §10).
EXCLUDED = [
    "patient_id",
    "synthetic_IBD_outcome",
    "synthetic_IBD_risk_probability",
    "dysbiosis_index_0_100",
    "microbial_risk_score_0_1",
    "metabolomic_risk_score_0_1",
    "oral_contraceptive_use",
]

# The 10 input categories the user fills in.
GROUPS = {
    "Demographic data": ["age_years", "sex", "BMI_kg_m2"],
    "Family history": ["family_history_IBD", "family_history_autoimmune"],
    "Diet": [
        "fiber_g_day", "fast_food_times_week", "ultra_processed_food_times_week",
        "fruit_vegetable_servings_day", "sugary_drinks_times_week", "red_processed_meat_times_week",
        "fermented_food_times_week", "fish_times_week", "dates_times_week", "fried_food_times_week",
    ],
    "Lifestyle": [
        "physical_activity_min_week", "sedentary_hours_day", "sleep_hours", "sleep_quality",
        "stress_level", "smoking", "vaping",
    ],
    "Medication and antibiotics": [
        "antibiotic_courses_year", "antibiotic_use_past_3_months", "broad_spectrum_antibiotic",
        "NSAID_use_times_month", "PPI_use", "childhood_antibiotic_exposure",
    ],
    "Birth mode and early life": [
        "birth_mode", "breastfeeding_months", "childhood_GI_infection", "childhood_infection_count",
    ],
    "Microbiome diversity": [
        "alpha_diversity_Shannon", "butyrate_producer_abundance_pct", "Faecalibacterium_abundance_pct",
        "Roseburia_abundance_pct", "Bacteroides_abundance_pct", "Proteobacteria_abundance_pct",
        "Firmicutes_Bacteroidetes_ratio",
    ],
    "Inflammatory biomarkers": ["fecal_calprotectin_ug_g", "CRP_mg_L", "vitamin_D_ng_mL"],
    "Metabolism related biomarkers": [
        "serum_butyrate_umol_L", "fecal_butyrate_umol_g", "primary_to_secondary_bile_acid_ratio",
        "tryptophan_ug_mL", "indole_3_acetic_acid_ug_mL", "palmitic_acid_ug_mL", "myristic_acid_ug_mL",
        "arachidonic_acid_ug_mL", "histidine_ug_mL", "total_triglycerides_mg_dL",
    ],
    "Red flags": [
        "perianal_fistula_history", "recurrent_aphthous_ulcers", "erythema_nodosum_history",
        "pyoderma_gangrenosum_history", "hidradenitis_suppurativa_history", "PSC_or_elevated_LFTs",
        "unprovoked_VTE_history", "appendectomy_history", "tonsillectomy_history",
    ],
}
FEATURES = [c for cols in GROUPS.values() for c in cols]

# Categorical encodings (README §11). Red-flag columns are already 0/1 in the data.
ORDINAL = {
    "sex": {"Female": 0, "Male": 1},
    "birth_mode": {"Vaginal": 0, "Cesarean": 1},
    "family_history_IBD": {
        "None": 0, "Second-degree relative": 1, "First-degree relative": 2,
        "Multiple first-degree relatives": 3,
    },
    "childhood_antibiotic_exposure": {"None": 0, "1-2 courses/year": 1, "3+ courses/year": 2},
    "sleep_quality": {"Good": 0, "Moderate": 1, "Poor": 2},
    "stress_level": {"Low": 0, "Moderate": 1, "High": 2},
}
YES_NO = {"No": 0, "Yes": 1}
YES_NO_COLS = [
    "family_history_autoimmune", "smoking", "vaping", "antibiotic_use_past_3_months",
    "broad_spectrum_antibiotic", "PPI_use", "childhood_GI_infection",
]
BINARY_01_COLS = GROUPS["Red flags"]

# Kept in the model but never shown as an explanation (README §8: synthetic direction mismatch).
NO_NARRATE = [
    "appendectomy_history", "childhood_infection_count",
    "total_triglycerides_mg_dL", "palmitic_acid_ug_mL",
]

DISCLAIMER = (
    "Synthetic data only. SHAP explanations reflect the synthetic generation formula, "
    "not real biology. Do not present these explanations as clinical evidence or diagnostic reasoning."
)

assert len(FEATURES) == 61 and len(set(FEATURES)) == 61
assert not set(FEATURES) & set(EXCLUDED)


def load_raw(path=DATA_PATH):
    # keep_default_na=False: the literal "None" in family_history_IBD /
    # childhood_antibiotic_exposure is a real category, not missing data.
    return pd.read_excel(path, sheet_name=SHEET, keep_default_na=False)


def encode(df):
    """Map human-readable inputs to the numeric matrix the model expects (columns = FEATURES)."""
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Missing input variables: {missing}")
    X = df[FEATURES].copy()
    for col, mapping in ORDINAL.items():
        X[col] = _map(X[col], mapping, col)
    for col in YES_NO_COLS:
        X[col] = _map(X[col], YES_NO, col)
    for col in BINARY_01_COLS:
        X[col] = _map(X[col].replace({"Yes": 1, "No": 0}), {0: 0, 1: 1, "0": 0, "1": 1}, col)
    for col in FEATURES:
        X[col] = pd.to_numeric(X[col], errors="raise") if X[col].dtype == object else X[col]
    return X.astype(float)


def _map(series, mapping, col):
    out = series.map(mapping)
    bad = series[out.isna()].unique()
    if len(bad):
        raise ValueError(f"{col}: unknown value(s) {list(bad)}; allowed: {list(mapping)}")
    return out


def decode_value(col, value):
    """Numeric code back to the human-readable label (for explanations)."""
    if col in ORDINAL:
        inv = {v: k for k, v in ORDINAL[col].items()}
        return inv.get(int(value), value)
    if col in YES_NO_COLS or col in BINARY_01_COLS:
        return "Yes" if int(value) == 1 else "No"
    return float(np.round(value, 3))

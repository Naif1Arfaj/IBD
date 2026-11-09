"""Feature definitions, encodings and governance rules for the IBD risk model.

All rules follow the README sheet of Saudi_IBD_Synthetic.xlsx (governance review 2026-10-07;
symptom and blood-test block added 2026-11-08, README §15).
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "Saudi_IBD_Synthetic.xlsx"
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

# Signs and symptoms, and routine blood tests, added 2026-11-08 (README §15). Recorded when available:
# a blank is imputed inside the model pipeline, so these inputs are optional.
SYMPTOMS = [
    "diarrhea", "constipation", "alternating_diarrhea_constipation", "bowel_movements_per_day",
    "increased_bowel_frequency", "stool_consistency_bristol", "blood_in_stool", "visible_rectal_bleeding",
    "mucus_in_stool", "nocturnal_bowel_movements", "urgency_defecation", "tenesmus", "change_in_bowel_habits",
    "abdominal_pain", "abdominal_pain_severity_0_10", "abdominal_pain_location", "abdominal_cramping",
    "abdominal_bloating", "excessive_gas_flatulence", "nausea", "vomiting", "loss_of_appetite",
    "unintentional_weight_loss", "symptom_duration_weeks", "symptom_frequency", "fatigue", "persistent_tiredness",
    "fever", "night_sweats", "unexplained_weight_loss", "reduced_energy_levels",
]
BLOOD_TESTS = ["anemia_status", "hemoglobin_g_dL", "WBC_10e9_L", "platelet_count_10e9_L", "MCV_fL", "ESR_mm_h"]
OPTIONAL = SYMPTOMS + BLOOD_TESTS

# The 11 input categories the user fills in.
GROUPS = {
    "Demographic data": ["age_years", "sex", "BMI_kg_m2"],
    "Signs and symptoms": SYMPTOMS,
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
    "Inflammatory biomarkers": ["fecal_calprotectin_ug_g", "CRP_mg_L", "vitamin_D_ng_mL", *BLOOD_TESTS],
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
    "symptom_frequency": {"None": 0, "Occasional": 1, "Intermittent": 2, "Frequent": 3, "Persistent": 4},
}
# Unordered categories become one 0/1 model column each; "None" (no abdominal pain) is the baseline.
NOMINAL = {
    "abdominal_pain_location": ["Diffuse", "Periumbilical", "Lower abdomen", "Left lower quadrant",
                                "Right lower quadrant", "Epigastric"],
}
# In the data these are blank exactly when there is no pain or no ongoing symptom, so a blank means "none".
BLANK_MEANS_NONE = {"abdominal_pain_location": "None", "symptom_frequency": "None", "symptom_duration_weeks": 0}
YES_NO = {"No": 0, "Yes": 1}
YES_NO_COLS = [
    "family_history_autoimmune", "smoking", "vaping", "antibiotic_use_past_3_months",
    "broad_spectrum_antibiotic", "PPI_use", "childhood_GI_infection",
]
BINARY_01_COLS = GROUPS["Red flags"]
# 0/1 symptoms and anaemia: unlike the red flags, a blank stays missing and is imputed.
OPTIONAL_BINARY_COLS = [c for c in OPTIONAL if c not in ORDINAL and c not in NOMINAL and c not in (
    "bowel_movements_per_day", "stool_consistency_bristol", "abdominal_pain_severity_0_10",
    "symptom_duration_weeks", "hemoglobin_g_dL", "WBC_10e9_L", "platelet_count_10e9_L", "MCV_fL", "ESR_mm_h")]

# The model's columns: the inputs, with each nominal input expanded into one column per category.
MODEL_COLUMNS = [col for f in FEATURES
                 for col in ([f"{f}={v}" for v in NOMINAL[f]] if f in NOMINAL else [f])]
COLUMN_FEATURE = {col: col.split("=", 1)[0] for col in MODEL_COLUMNS}

# Kept in the model but never shown as an explanation (README §8: synthetic direction mismatch).
NO_NARRATE = [
    "appendectomy_history", "childhood_infection_count",
    "total_triglycerides_mg_dL", "palmitic_acid_ug_mL",
    # 2026-11-09 retraining: in this synthetic data these lower the estimate, the opposite of clinical expectation.
    "anemia_status", "nausea",
]

DISCLAIMER = (
    "Synthetic data only. SHAP explanations reflect the synthetic generation formula, "
    "not real biology. Do not present these explanations as clinical evidence or diagnostic reasoning."
)

assert len(FEATURES) == 98 and len(set(FEATURES)) == 98 and len(OPTIONAL) == 37
assert len(OPTIONAL_BINARY_COLS) == 26
assert not set(FEATURES) & set(EXCLUDED)


def load_raw(path=DATA_PATH):
    # keep_default_na=False: the literal "None" in family_history_IBD /
    # childhood_antibiotic_exposure is a real category, not missing data.
    raw = pd.read_excel(path, sheet_name=SHEET, keep_default_na=False)
    for col in OPTIONAL:  # only the new columns have genuinely blank cells
        raw[col] = raw[col].map(lambda v: np.nan if v == "" else v)
        if col not in ORDINAL and col not in NOMINAL:
            raw[col] = pd.to_numeric(raw[col])
    return raw


def is_blank(value):
    return value is None or value == "" or (isinstance(value, float) and np.isnan(value))


def json_value(value):
    """A dataset cell as a JSON-safe Python value: numpy scalars unwrapped, blanks as None."""
    value = value.item() if hasattr(value, "item") else value
    return None if is_blank(value) else value


def encode(df):
    """Map human-readable inputs to the numeric matrix the model expects (columns = MODEL_COLUMNS).

    The original 61 inputs are required. The optional inputs may be absent or blank: they stay NaN and the
    model pipeline imputes them, except where a blank means "none" (BLANK_MEANS_NONE).
    """
    missing = [c for c in FEATURES if c not in df.columns and c not in OPTIONAL]
    if missing:
        raise ValueError(f"Missing input variables: {missing}")
    X = df.reindex(columns=FEATURES).copy()
    for col in OPTIONAL:
        X[col] = X[col].map(lambda v: np.nan if is_blank(v) else v)
    for col, none_value in BLANK_MEANS_NONE.items():
        X[col] = X[col].where(X[col].notna(), none_value)
    for col, mapping in ORDINAL.items():
        X[col] = _map(X[col], mapping, col)
    for col in YES_NO_COLS:
        X[col] = _map(X[col], YES_NO, col)
    for col in BINARY_01_COLS:
        X[col] = _map(X[col].replace({"Yes": 1, "No": 0}), {0: 0, 1: 1, "0": 0, "1": 1}, col)
    for col in OPTIONAL_BINARY_COLS:
        X[col] = _map(X[col].replace({"Yes": 1, "No": 0}), {0: 0, 1: 1, "0": 0, "1": 1}, col, keep_blank=True)
    for col, categories in NOMINAL.items():
        unknown = set(X[col].dropna()) - set(categories) - {"None"}
        if unknown:
            raise ValueError(f"{col}: unknown value(s) {sorted(unknown)}; allowed: {['None', *categories]}")
        for category in categories:
            X[f"{col}={category}"] = (X[col] == category).astype(float)
    for col in FEATURES:
        if col not in NOMINAL and X[col].dtype == object:
            X[col] = pd.to_numeric(X[col], errors="raise")
    return X[MODEL_COLUMNS].astype(float)


def _map(series, mapping, col, keep_blank=False):
    out = series.map(mapping)
    bad = series[out.isna() & ~(keep_blank & series.isna())].unique()
    if len(bad):
        raise ValueError(f"{col}: unknown value(s) {list(bad)}; allowed: {list(mapping)}")
    return out


def by_feature(values):
    """Model-column values (e.g. SHAP, shape (..., n_columns)) summed back to one value per input."""
    values = np.asarray(values, dtype=float)
    index = {f: i for i, f in enumerate(FEATURES)}
    out = np.zeros(values.shape[:-1] + (len(FEATURES),))
    for j, col in enumerate(MODEL_COLUMNS):
        out[..., index[COLUMN_FEATURE[col]]] += values[..., j]
    return out


def feature_value(feature, x_row):
    """One input's human-readable value from an encoded model row (for explanations)."""
    if feature in NOMINAL:
        chosen = [v for v in NOMINAL[feature] if x_row[f"{feature}={v}"] == 1]
        return chosen[0] if chosen else "None"
    return decode_value(feature, x_row[feature])


def decode_value(col, value):
    """Numeric code back to the human-readable label (for explanations)."""
    if is_blank(value):
        return "Not recorded"
    if col in ORDINAL:
        inv = {v: k for k, v in ORDINAL[col].items()}
        return inv.get(int(value), value)
    if col in YES_NO_COLS or col in BINARY_01_COLS or col in OPTIONAL_BINARY_COLS:
        return "Yes" if int(value) == 1 else "No"
    return float(np.round(value, 3))

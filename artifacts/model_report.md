# IBD risk model — training report

> **Synthetic data only. SHAP explanations reflect the synthetic generation formula, not real biology. Do not present these explanations as clinical evidence or diagnostic reasoning.**
> All metrics below measure how well the model recovers the *synthetic generation formula*.
> They are **not** evidence of clinical or diagnostic accuracy.

## Data
- Source: `Saudi_IBD_Synthetic.xlsx`, sheet `Synthetic_Data` — 2500 rows, IBD prevalence 24.7%
- Inputs: **98** (103 model columns; abdominal pain location is one-hot encoded):
  the original 61 (README Option A minus `oral_contraceptive_use`) plus 37 signs, symptoms and blood tests
  (README §15). Excluded: `patient_id`, `synthetic_IBD_outcome`, `synthetic_IBD_risk_probability`, `dysbiosis_index_0_100`, `microbial_risk_score_0_1`, `metabolomic_risk_score_0_1`, `oral_contraceptive_use`
- Not used from the README §15 block: `fecal_occult_blood_test_positive` and the 5 current extra-intestinal symptoms
- Missing values: blank optional inputs are imputed with the training-fold median inside every pipeline. A blank
  pain location, symptom frequency or symptom duration means none (no pain or no ongoing symptoms)
- `anemia_status` is derived from `hemoglobin_g_dL` and sex, so their attributions share one signal
- Split: stratified 80/20 (train 2000, test 500), seed 42
- Model comparison: nested 5-fold CV on the training set (hyperparameters tuned inside each fold on PR-AUC)

## Model comparison (out-of-fold, training set)
Precision / recall / accuracy are at each model's own threshold (max F1 with recall ≥ 0.85).

| model                                          |   PR_AUC |   ROC_AUC |   Brier |   precision |   recall |   accuracy |    F1 |
|:-----------------------------------------------|---------:|----------:|--------:|------------:|---------:|-----------:|------:|
| Sparse Logistic Regression (L1)                |    0.942 |     0.979 |   0.05  |       0.864 |    0.864 |      0.933 | 0.864 |
| Ensemble (Sparse Logistic Regression + HistGB) |    0.936 |     0.977 |   0.052 |       0.847 |    0.852 |      0.925 | 0.85  |
| Logistic Regression (L2)                       |    0.932 |     0.977 |   0.056 |       0.854 |    0.85  |      0.927 | 0.852 |
| Logistic Regression + splines                  |    0.93  |     0.975 |   0.059 |       0.841 |    0.864 |      0.926 | 0.852 |
| Gradient Boosting (HistGB)                     |    0.908 |     0.964 |   0.064 |       0.819 |    0.85  |      0.916 | 0.834 |
| Random Forest                                  |    0.905 |     0.964 |   0.081 |       0.769 |    0.868 |      0.903 | 0.816 |

**Chosen model: Sparse Logistic Regression (L1)** — highest out-of-fold PR-AUC.
Final hyperparameters (tuned on all data): `{'clf__C': 0.1}`

## Decision threshold
- Rule: maximize F1 subject to recall ≥ 0.85 on out-of-fold training predictions → **0.462**
- Risk tiers on the predicted probability: Low < 0.2 ≤ Moderate < 0.5 ≤ High

### Precision at each recall level (out-of-fold, training set)
|   target_recall |   recall |   precision |   threshold |   accuracy |
|----------------:|---------:|------------:|------------:|-----------:|
|            0.7  |    0.719 |       0.942 |       0.687 |      0.919 |
|            0.75 |    0.751 |       0.93  |       0.65  |      0.924 |
|            0.8  |    0.806 |       0.9   |       0.571 |      0.93  |
|            0.85 |    0.85  |       0.871 |       0.477 |      0.932 |
|            0.9  |    0.901 |       0.815 |       0.37  |      0.925 |
|            0.95 |    0.951 |       0.756 |       0.272 |      0.912 |
|            0.98 |    0.982 |       0.645 |       0.149 |      0.862 |

## Held-out test set (500 people, never used for training or tuning)
| Metric | Value |
|---|---|
| ROC-AUC (95% bootstrap CI) | 0.977 (0.966–0.987) |
| PR-AUC | 0.937 |
| **Precision** (PPV) | **0.843** |
| **Recall** (sensitivity) | **0.863** |
| **Accuracy** | **0.926** |
| F1 | 0.853 |
| Specificity | 0.947 |
| NPV | 0.954 |
| Brier score | 0.054 |
| Calibration slope / intercept | 1.42 / -0.10 |

|                |   Predicted: No IBD |   Predicted: IBD |
|:---------------|--------------------:|-----------------:|
| Actual: No IBD |                 356 |               20 |
| Actual: IBD    |                  17 |              107 |

### Precision at each recall level (test set)
|   target_recall |   recall |   precision |   threshold |   accuracy |
|----------------:|---------:|------------:|------------:|-----------:|
|            0.7  |    0.726 |       0.928 |       0.69  |      0.918 |
|            0.75 |    0.766 |       0.913 |       0.601 |      0.924 |
|            0.8  |    0.823 |       0.895 |       0.509 |      0.932 |
|            0.85 |    0.863 |       0.849 |       0.469 |      0.928 |
|            0.9  |    0.903 |       0.778 |       0.385 |      0.912 |
|            0.95 |    0.952 |       0.728 |       0.285 |      0.9   |
|            0.98 |    0.984 |       0.635 |       0.168 |      0.856 |

## Explainability (SHAP, final model)
Importance by input group (sum of mean |SHAP|):

| group                         |   sum mean |SHAP| |
|:------------------------------|------------------:|
| Metabolism related biomarkers |             2.306 |
| Microbiome diversity          |             1.397 |
| Diet                          |             1.297 |
| Inflammatory biomarkers       |             1.164 |
| Signs and symptoms            |             0.907 |
| Medication and antibiotics    |             0.74  |
| Family history                |             0.298 |
| Birth mode and early life     |             0.215 |
| Lifestyle                     |             0.18  |
| Red flags                     |             0.071 |
| Demographic data              |             0     |

Top 10 features: `fecal_butyrate_umol_g`, `fecal_calprotectin_ug_g`, `alpha_diversity_Shannon`, `antibiotic_courses_year`, `ultra_processed_food_times_week`, `fiber_g_day`, `serum_butyrate_umol_L`, `Proteobacteria_abundance_pct`, `primary_to_secondary_bile_acid_ratio`, `fast_food_times_week`

### V6 sanity checks
- Excluded columns absent from the feature matrix: **yes** (asserted in code)
- Composites and components not mixed: **yes** (composites excluded, Option A)
- SHAP direction vs published evidence:

| feature                      | expected   | model   | match   |
|:-----------------------------|:-----------|:--------|:--------|
| fiber_g_day                  | lowers     | lowers  | yes     |
| alpha_diversity_Shannon      | lowers     | lowers  | yes     |
| serum_butyrate_umol_L        | lowers     | lowers  | yes     |
| fecal_butyrate_umol_g        | lowers     | lowers  | yes     |
| vitamin_D_ng_mL              | lowers     | lowers  | yes     |
| fecal_calprotectin_ug_g      | raises     | raises  | yes     |
| Proteobacteria_abundance_pct | raises     | raises  | yes     |
| antibiotic_courses_year      | raises     | raises  | yes     |
| blood_in_stool               | raises     | raises  | yes     |
| visible_rectal_bleeding      | raises     | raises  | yes     |
| nocturnal_bowel_movements    | raises     | raises  | yes     |
| unexplained_weight_loss      | raises     | unused (zero weight) | n/a |
| ESR_mm_h                     | raises     | unused (zero weight) | n/a |

- Low-signal variables (README §9) — importance rank out of 98 (higher = less important):
  `stress_level` #25, `childhood_antibiotic_exposure` #34, `PPI_use` #41, `physical_activity_min_week` #44, `fruit_vegetable_servings_day` #54, `breastfeeding_months` #58, `childhood_GI_infection` #71, `NSAID_use_times_month` #72, `BMI_kg_m2` #73, `red_processed_meat_times_week` #91
- Never narrated in explanations (README §8 and the symptom-direction review): `appendectomy_history`, `childhood_infection_count`, `total_triglycerides_mg_dL`, `palmitic_acid_ug_mL`, `anemia_status`, `nausea` (the last two lower the estimate in this synthetic data, the opposite of clinical expectation)

### Signs, symptoms and blood tests (new inputs)
| input                             |   importance rank |   mean abs SHAP | direction   |
|:----------------------------------|------------------:|----------------:|:------------|
| constipation                      |                12 |           0.248 | lowers      |
| blood_in_stool                    |                20 |           0.147 | raises      |
| symptom_duration_weeks            |                26 |           0.079 | raises      |
| loss_of_appetite                  |                27 |           0.077 | raises      |
| urgency_defecation                |                31 |           0.067 | raises      |
| anemia_status                     |                32 |           0.066 | lowers      |
| nocturnal_bowel_movements         |                33 |           0.065 | raises      |
| unintentional_weight_loss         |                36 |           0.039 | raises      |
| bowel_movements_per_day           |                37 |           0.037 | raises      |
| tenesmus                          |                38 |           0.035 | raises      |
| stool_consistency_bristol         |                39 |           0.034 | raises      |
| symptom_frequency                 |                40 |           0.034 | raises      |
| nausea                            |                45 |           0.020 | lowers      |
| MCV_fL                            |                46 |           0.018 | raises      |
| abdominal_pain_location           |                48 |           0.014 | unused (zero weight) |
| persistent_tiredness              |                52 |           0.012 | raises      |
| visible_rectal_bleeding           |                60 |           0.001 | raises      |
| hemoglobin_g_dL                   |                63 |           0.000 | unused (zero weight) |
| WBC_10e9_L                        |                64 |           0.000 | unused (zero weight) |
| platelet_count_10e9_L             |                65 |           0.000 | unused (zero weight) |
| ESR_mm_h                          |                67 |           0.000 | unused (zero weight) |
| diarrhea                          |                74 |           0.000 | unused (zero weight) |
| alternating_diarrhea_constipation |                75 |           0.000 | unused (zero weight) |
| increased_bowel_frequency         |                76 |           0.000 | unused (zero weight) |
| mucus_in_stool                    |                77 |           0.000 | unused (zero weight) |
| change_in_bowel_habits            |                78 |           0.000 | unused (zero weight) |
| abdominal_pain                    |                79 |           0.000 | unused (zero weight) |
| abdominal_pain_severity_0_10      |                80 |           0.000 | unused (zero weight) |
| abdominal_cramping                |                81 |           0.000 | unused (zero weight) |
| abdominal_bloating                |                82 |           0.000 | unused (zero weight) |
| excessive_gas_flatulence          |                83 |           0.000 | unused (zero weight) |
| vomiting                          |                84 |           0.000 | unused (zero weight) |
| fatigue                           |                85 |           0.000 | unused (zero weight) |
| fever                             |                86 |           0.000 | unused (zero weight) |
| night_sweats                      |                87 |           0.000 | unused (zero weight) |
| unexplained_weight_loss           |                88 |           0.000 | unused (zero weight) |
| reduced_energy_levels             |                89 |           0.000 | unused (zero weight) |

## Files
- `model.joblib` — final model (refit on all 2500 rows), threshold, tiers, feature order, defaults
- `roc_pr.png`, `calibration.png`, `shap_summary.png`

_Training time: 600s_

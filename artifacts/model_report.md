# IBD risk model — training report

> **Synthetic data only. SHAP explanations reflect the synthetic generation formula, not real biology. Do not present these explanations as clinical evidence or diagnostic reasoning.**
> All metrics below measure how well the model recovers the *synthetic generation formula*.
> They are **not** evidence of clinical or diagnostic accuracy.

## Data
- Source: `Saudi_IBD_Synthetic.xlsx`, sheet `Synthetic_Data` — 2500 rows, IBD prevalence 24.7%
- Features: **61** (README Option A minus `oral_contraceptive_use`). Excluded: `patient_id`, `synthetic_IBD_outcome`, `synthetic_IBD_risk_probability`, `dysbiosis_index_0_100`, `microbial_risk_score_0_1`, `metabolomic_risk_score_0_1`, `oral_contraceptive_use`
- Split: stratified 80/20 (train 2000, test 500), seed 42
- Model comparison: nested 5-fold CV on the training set (hyperparameters tuned inside each fold on PR-AUC)

## Model comparison (out-of-fold, training set)
Precision / recall / accuracy are at each model's own threshold (max F1 with recall ≥ 0.85).

| model                                          |   PR_AUC |   ROC_AUC |   Brier |   precision |   recall |   accuracy |    F1 |
|:-----------------------------------------------|---------:|----------:|--------:|------------:|---------:|-----------:|------:|
| Sparse Logistic Regression (L1)                |    0.935 |     0.975 |   0.053 |       0.867 |    0.86  |      0.933 | 0.864 |
| Logistic Regression (L2)                       |    0.929 |     0.973 |   0.053 |       0.87  |    0.856 |      0.933 | 0.863 |
| Ensemble (Sparse Logistic Regression + HistGB) |    0.929 |     0.973 |   0.056 |       0.837 |    0.854 |      0.923 | 0.846 |
| Logistic Regression + splines                  |    0.924 |     0.972 |   0.062 |       0.827 |    0.858 |      0.92  | 0.842 |
| Gradient Boosting (HistGB)                     |    0.903 |     0.961 |   0.069 |       0.756 |    0.864 |      0.897 | 0.806 |
| Random Forest                                  |    0.893 |     0.96  |   0.082 |       0.751 |    0.862 |      0.895 | 0.803 |

**Chosen model: Sparse Logistic Regression (L1)** — highest out-of-fold PR-AUC.
Final hyperparameters (tuned on all data): `{'clf__C': 0.3}`

## Decision threshold
- Rule: maximize F1 subject to recall ≥ 0.85 on out-of-fold training predictions → **0.454**
- Risk tiers on the predicted probability: Low < 0.2 ≤ Moderate < 0.5 ≤ High

### Precision at each recall level (out-of-fold, training set)
|   target_recall |   recall |   precision |   threshold |   accuracy |
|----------------:|---------:|------------:|------------:|-----------:|
|            0.7  |    0.702 |       0.93  |       0.708 |      0.913 |
|            0.75 |    0.759 |       0.921 |       0.648 |      0.924 |
|            0.8  |    0.802 |       0.904 |       0.576 |      0.93  |
|            0.85 |    0.85  |       0.871 |       0.47  |      0.932 |
|            0.9  |    0.901 |       0.777 |       0.3   |      0.911 |
|            0.95 |    0.951 |       0.665 |       0.165 |      0.87  |
|            0.98 |    0.982 |       0.617 |       0.111 |      0.845 |

## Held-out test set (500 people, never used for training or tuning)
| Metric | Value |
|---|---|
| ROC-AUC (95% bootstrap CI) | 0.972 (0.959–0.983) |
| PR-AUC | 0.925 |
| **Precision** (PPV) | **0.800** |
| **Recall** (sensitivity) | **0.806** |
| **Accuracy** | **0.902** |
| F1 | 0.803 |
| Specificity | 0.934 |
| NPV | 0.936 |
| Brier score | 0.059 |
| Calibration slope / intercept | 1.00 / -0.08 |

|                |   Predicted: No IBD |   Predicted: IBD |
|:---------------|--------------------:|-----------------:|
| Actual: No IBD |                 351 |               25 |
| Actual: IBD    |                  24 |              100 |

### Precision at each recall level (test set)
|   target_recall |   recall |   precision |   threshold |   accuracy |
|----------------:|---------:|------------:|------------:|-----------:|
|            0.7  |    0.702 |       0.916 |       0.715 |      0.91  |
|            0.75 |    0.758 |       0.87  |       0.593 |      0.912 |
|            0.8  |    0.815 |       0.802 |       0.452 |      0.904 |
|            0.85 |    0.887 |       0.797 |       0.354 |      0.916 |
|            0.9  |    0.903 |       0.783 |       0.33  |      0.914 |
|            0.95 |    0.96  |       0.748 |       0.244 |      0.91  |
|            0.98 |    0.984 |       0.674 |       0.136 |      0.878 |

## Explainability (SHAP, final model)
Importance by input group (sum of mean |SHAP|):

| group                         |   sum mean |SHAP| |
|:------------------------------|------------------:|
| Metabolism related biomarkers |             2.915 |
| Microbiome diversity          |             2.028 |
| Diet                          |             1.863 |
| Inflammatory biomarkers       |             1.423 |
| Medication and antibiotics    |             1.097 |
| Family history                |             0.458 |
| Lifestyle                     |             0.454 |
| Birth mode and early life     |             0.353 |
| Red flags                     |             0.224 |
| Demographic data              |             0.013 |

Top 10 features: `fecal_calprotectin_ug_g`, `fecal_butyrate_umol_g`, `alpha_diversity_Shannon`, `ultra_processed_food_times_week`, `antibiotic_courses_year`, `fiber_g_day`, `Proteobacteria_abundance_pct`, `serum_butyrate_umol_L`, `fast_food_times_week`, `indole_3_acetic_acid_ug_mL`

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

- Low-signal variables (README §9) — importance rank out of 61 (higher = less important):
  `stress_level` #23, `physical_activity_min_week` #26, `fruit_vegetable_servings_day` #29, `childhood_antibiotic_exposure` #30, `breastfeeding_months` #32, `PPI_use` #41, `NSAID_use_times_month` #46, `red_processed_meat_times_week` #54, `childhood_GI_infection` #55, `BMI_kg_m2` #61
- Never narrated in explanations (README §8): `appendectomy_history`, `childhood_infection_count`, `total_triglycerides_mg_dL`, `palmitic_acid_ug_mL`

## Files
- `model.joblib` — final model (refit on all 2500 rows), threshold, tiers, feature order, defaults
- `roc_pr.png`, `calibration.png`, `shap_summary.png`

_Training time: 331s_

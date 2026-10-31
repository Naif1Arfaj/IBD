"""Train, compare and select an IBD classifier on the synthetic Saudi dataset.

Run:  .venv/bin/python train.py
Outputs go to artifacts/ (model.joblib, model_report.md, plots).
"""
import time
import warnings
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from explain import top_factors, make_explainer
from features import BINARY_01_COLS, DISCLAIMER, EXCLUDED, FEATURES, GROUPS, ORDINAL, YES_NO_COLS, encode, load_raw

warnings.filterwarnings("ignore")
SEED = 42
MIN_RECALL = 0.85
TIERS = {"Low": 0.20, "Moderate": 0.50}  # p < 0.20 Low, 0.20-0.50 Moderate, >= 0.50 High
OUT = Path(__file__).resolve().parent / "artifacts"
OUT.mkdir(exist_ok=True)

CONTINUOUS = [c for c in FEATURES if c not in ORDINAL and c not in YES_NO_COLS and c not in BINARY_01_COLS]


def candidates():
    inner = StratifiedKFold(5, shuffle=True, random_state=SEED + 1)
    ap = "average_precision"
    lr = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=5000))])
    lr_l1 = Pipeline([("scale", StandardScaler()),
                      ("clf", LogisticRegression(penalty="l1", solver="liblinear", max_iter=5000))])
    spline = Pipeline([
        ("prep", ColumnTransformer(
            [("spl", SplineTransformer(n_knots=4, degree=3), CONTINUOUS)],
            remainder="passthrough")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=5000)),
    ])
    hgb = HistGradientBoostingClassifier(random_state=SEED, early_stopping=False)
    rf = RandomForestClassifier(n_estimators=500, random_state=SEED, n_jobs=-1)
    Cs = [0.01, 0.03, 0.1, 0.3, 1, 3]
    return {
        "Logistic Regression (L2)": GridSearchCV(lr, {"clf__C": Cs}, scoring=ap, cv=inner),
        "Sparse Logistic Regression (L1)": GridSearchCV(lr_l1, {"clf__C": Cs}, scoring=ap, cv=inner),
        "Logistic Regression + splines": GridSearchCV(spline, {"clf__C": [0.003, 0.01, 0.03, 0.1]}, scoring=ap, cv=inner),
        "Random Forest": GridSearchCV(rf, {"min_samples_leaf": [1, 3, 5], "max_features": ["sqrt", 0.3]},
                                      scoring=ap, cv=inner, n_jobs=1),
        "Gradient Boosting (HistGB)": RandomizedSearchCV(
            hgb, {"learning_rate": [0.02, 0.05, 0.1], "max_iter": [200, 400, 800], "max_depth": [2, 3, 4, None],
                  "min_samples_leaf": [10, 20, 40], "l2_regularization": [0, 0.1, 1.0]},
            n_iter=15, scoring=ap, cv=inner, random_state=SEED),
    }


def pick_threshold(y, p, min_recall=MIN_RECALL):
    """Threshold that maximizes F1 among thresholds with recall >= min_recall."""
    best_t, best_f1 = 0.5, -1
    for t in np.unique(np.round(p, 4)):
        yh = (p >= t).astype(int)
        r = recall_score(y, yh)
        if r < min_recall:
            continue
        f = f1_score(y, yh)
        if f > best_f1:
            best_t, best_f1 = float(t), f
    return best_t


def metrics_at(y, p, t):
    yh = (p >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh).ravel()
    return {
        "threshold": t, "accuracy": accuracy_score(y, yh), "precision": precision_score(y, yh),
        "recall": recall_score(y, yh), "specificity": tn / (tn + fp), "f1": f1_score(y, yh),
        "npv": tn / (tn + fn), "TP": int(tp), "FN": int(fn), "FP": int(fp), "TN": int(tn),
    }


def precision_at_recall_table(y, p, levels=(0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98)):
    P, R, T = precision_recall_curve(y, p)
    rows = []
    for lv in levels:
        idx = np.where(R[:-1] >= lv)[0]
        i = idx[np.argmax(P[idx])]
        rows.append({"target_recall": lv, "recall": R[i], "precision": P[i], "threshold": T[i],
                     "accuracy": accuracy_score(y, (p >= T[i]).astype(int))})
    return pd.DataFrame(rows)


def calibration_slope_intercept(y, p):
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    m = LogisticRegression(C=1e6, max_iter=5000).fit(lp.reshape(-1, 1), y)
    return float(m.coef_[0, 0]), float(m.intercept_[0])


def bootstrap_auc_ci(y, p, n=2000):
    rng = np.random.default_rng(SEED)
    aucs = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            aucs.append(roc_auc_score(y[i], p[i]))
    return np.percentile(aucs, [2.5, 97.5])


def fmt(df, cols_pct=()):
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: f"{v:.3f}")
    return d.to_markdown(index=False) if hasattr(d, "to_markdown") else d.to_string(index=False)


def main():
    t0 = time.time()
    raw = load_raw()
    X = encode(raw)
    y = raw["synthetic_IBD_outcome"].astype(int).values
    assert list(X.columns) == FEATURES and X.shape[1] == 61
    assert not set(X.columns) & set(EXCLUDED), "leakage column in features"
    assert not X.isna().any().any()
    print(f"Data: {X.shape[0]} rows, {X.shape[1]} features, prevalence {y.mean():.3f}")

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    outer = StratifiedKFold(5, shuffle=True, random_state=SEED)

    # 1) Nested CV on the training set: tuning inside, out-of-fold predictions outside.
    oof, rows, fitted = {}, [], {}
    for name, search in candidates().items():
        s = time.time()
        p = cross_val_predict(search, X_tr, y_tr, cv=outer, method="predict_proba")[:, 1]
        oof[name] = p
        t = pick_threshold(y_tr, p)
        m = metrics_at(y_tr, p, t)
        rows.append({"model": name, "PR_AUC": average_precision_score(y_tr, p), "ROC_AUC": roc_auc_score(y_tr, p),
                     "Brier": brier_score_loss(y_tr, p), "precision": m["precision"], "recall": m["recall"],
                     "accuracy": m["accuracy"], "F1": m["f1"]})
        fitted[name] = search
        print(f"  {name:34s} PR-AUC {rows[-1]['PR_AUC']:.3f}  ROC-AUC {rows[-1]['ROC_AUC']:.3f}  "
              f"P {m['precision']:.3f} R {m['recall']:.3f} Acc {m['accuracy']:.3f}  ({time.time()-s:.0f}s)")

    # Soft-voting ensemble of the best linear model and gradient boosting.
    lin_names = ["Logistic Regression (L2)", "Sparse Logistic Regression (L1)", "Logistic Regression + splines"]
    best_lin = max(lin_names, key=lambda n: average_precision_score(y_tr, oof[n]))
    ens_name = f"Ensemble ({best_lin.split(' (')[0].split(' +')[0]} + HistGB)"
    p = (oof[best_lin] + oof["Gradient Boosting (HistGB)"]) / 2
    oof[ens_name] = p
    t = pick_threshold(y_tr, p)
    m = metrics_at(y_tr, p, t)
    rows.append({"model": ens_name, "PR_AUC": average_precision_score(y_tr, p), "ROC_AUC": roc_auc_score(y_tr, p),
                 "Brier": brier_score_loss(y_tr, p), "precision": m["precision"], "recall": m["recall"],
                 "accuracy": m["accuracy"], "F1": m["f1"]})
    print(f"  {ens_name:34s} PR-AUC {rows[-1]['PR_AUC']:.3f}  ROC-AUC {rows[-1]['ROC_AUC']:.3f}  "
          f"P {m['precision']:.3f} R {m['recall']:.3f} Acc {m['accuracy']:.3f}")

    cmp = pd.DataFrame(rows).sort_values("PR_AUC", ascending=False).reset_index(drop=True)

    # 2) Selection: best PR-AUC; within 0.005 prefer the simpler model (list order = simplicity).
    simplicity = lin_names + ["Random Forest", "Gradient Boosting (HistGB)", ens_name]
    top = cmp["PR_AUC"].max()
    near = cmp[cmp["PR_AUC"] >= top - 0.005]["model"].tolist()
    chosen = min(near, key=simplicity.index)
    reason = (f"highest out-of-fold PR-AUC" if chosen == cmp.loc[0, "model"]
              else f"within 0.005 PR-AUC of the best ({cmp.loc[0, 'model']}) and simpler/more interpretable")
    print(f"\nChosen: {chosen} ({reason})")

    # 3) Threshold from out-of-fold predictions on train (never from test).
    threshold = pick_threshold(y_tr, oof[chosen])
    print(f"Threshold (max F1 with recall >= {MIN_RECALL}): {threshold:.3f}")

    best_params = {}

    def build(name, Xf, yf):
        if name == ens_name:
            sa = clone(fitted[best_lin]).fit(Xf, yf)
            sb = clone(fitted["Gradient Boosting (HistGB)"]).fit(Xf, yf)
            best_params.update({"linear": sa.best_params_, "gradient_boosting": sb.best_params_})
            return VotingClassifier([("lin", sa.best_estimator_), ("gb", sb.best_estimator_)],
                                    voting="soft").fit(Xf, yf)
        search = clone(fitted[name]).fit(Xf, yf)
        best_params.update(search.best_params_)
        return search.best_estimator_

    # 4) Held-out test evaluation (fit on train only).
    model_tr = build(chosen, X_tr, y_tr)
    p_te = model_tr.predict_proba(X_te)[:, 1]
    test = metrics_at(y_te, p_te, threshold)
    test.update({"ROC_AUC": roc_auc_score(y_te, p_te), "PR_AUC": average_precision_score(y_te, p_te),
                 "Brier": brier_score_loss(y_te, p_te)})
    lo, hi = bootstrap_auc_ci(y_te, p_te)
    slope, intercept = calibration_slope_intercept(y_te, p_te)
    print(f"TEST  ROC-AUC {test['ROC_AUC']:.3f} [{lo:.3f}-{hi:.3f}]  PR-AUC {test['PR_AUC']:.3f}  "
          f"Precision {test['precision']:.3f}  Recall {test['recall']:.3f}  Accuracy {test['accuracy']:.3f}  "
          f"F1 {test['f1']:.3f}")
    par_oof = precision_at_recall_table(y_tr, oof[chosen])
    par_test = precision_at_recall_table(y_te, p_te)

    # 5) Plots.
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    fpr, tpr, _ = roc_curve(y_te, p_te)
    ax[0].plot(fpr, tpr, color="#1f6f5c", lw=2, label=f"AUC {test['ROC_AUC']:.3f}")
    ax[0].plot([0, 1], [0, 1], ls="--", color="#999")
    ax[0].set(title="ROC curve (test set)", xlabel="False positive rate", ylabel="Recall (sensitivity)")
    ax[0].legend(loc="lower right")
    P, R, _ = precision_recall_curve(y_te, p_te)
    ax[1].plot(R, P, color="#1f6f5c", lw=2, label=f"PR-AUC {test['PR_AUC']:.3f}")
    ax[1].scatter([test["recall"]], [test["precision"]], color="#c0392b", zorder=3,
                  label=f"chosen threshold {threshold:.2f}")
    ax[1].set(title="Precision-recall curve (test set)", xlabel="Recall", ylabel="Precision", ylim=(0, 1.02))
    ax[1].legend(loc="lower left")
    fig.suptitle(f"{chosen} — synthetic data only", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "roc_pr.png", dpi=150)
    plt.close(fig)

    frac_pos, mean_pred = calibration_curve(y_te, p_te, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], ls="--", color="#999", label="perfect")
    ax.plot(mean_pred, frac_pos, marker="o", color="#1f6f5c", label=f"model (Brier {test['Brier']:.3f})")
    ax.set(title="Calibration (test set)", xlabel="Predicted probability", ylabel="Observed IBD fraction")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "calibration.png", dpi=150)
    plt.close(fig)

    # 6) Final model: refit on all 2,500 rows with the same hyperparameters and threshold.
    final = build(chosen, X, y)
    explainer = make_explainer(final, X)
    shap_X = X.sample(300, random_state=SEED)
    sv = explainer(shap_X)
    mean_abs = pd.Series(np.abs(sv).mean(0), index=FEATURES).sort_values(ascending=False)
    mean_signed_corr = {c: np.corrcoef(shap_X[c], sv[:, i])[0, 1]
                        if shap_X[c].std() > 0 else 0 for i, c in enumerate(FEATURES)}

    fig, ax = plt.subplots(figsize=(7, 8))
    top20 = mean_abs.head(20)[::-1]
    colors = ["#c0392b" if mean_signed_corr[c] > 0 else "#1f6f5c" for c in top20.index]
    ax.barh(top20.index, top20.values, color=colors)
    ax.set_title("Top 20 features by mean |SHAP|\nred = raises risk, green = lowers risk", fontsize=11)
    ax.set_xlabel("mean |SHAP| (log-odds)")
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "shap_summary.png", dpi=150)
    plt.close(fig)

    # SHAP sanity checks (README V6).
    expected = {"fiber_g_day": -1, "alpha_diversity_Shannon": -1, "serum_butyrate_umol_L": -1,
                "fecal_butyrate_umol_g": -1, "vitamin_D_ng_mL": -1, "fecal_calprotectin_ug_g": 1,
                "Proteobacteria_abundance_pct": 1, "antibiotic_courses_year": 1}
    sign_rows = [{"feature": f, "expected": "raises" if s > 0 else "lowers",
                  "model": "raises" if mean_signed_corr[f] > 0 else "lowers",
                  "match": "yes" if np.sign(mean_signed_corr[f]) == s else "NO"} for f, s in expected.items()]
    low_signal = ["childhood_antibiotic_exposure", "breastfeeding_months", "physical_activity_min_week",
                  "red_processed_meat_times_week", "fruit_vegetable_servings_day", "NSAID_use_times_month",
                  "BMI_kg_m2", "stress_level", "PPI_use", "childhood_GI_infection"]
    low_rank = {c: int(mean_abs.index.get_loc(c)) + 1 for c in low_signal}

    joblib.dump({
        "model": final, "model_name": chosen, "threshold": threshold, "tiers": TIERS,
        "feature_order": FEATURES, "groups": GROUPS,
        "defaults": {c: (raw[c].mode()[0] if raw[c].dtype == object else float(raw[c].median())) for c in FEATURES},
        "background": X.sample(200, random_state=SEED),
        "test_metrics": test, "disclaimer": DISCLAIMER,
    }, OUT / "model.joblib")

    # 7) Report.
    group_imp = {g: float(mean_abs[cols].sum()) for g, cols in GROUPS.items()}
    gi = pd.DataFrame(sorted(group_imp.items(), key=lambda kv: -kv[1]), columns=["group", "sum mean |SHAP|"])
    cm = pd.DataFrame([[test["TN"], test["FP"]], [test["FN"], test["TP"]]],
                      index=["Actual: No IBD", "Actual: IBD"], columns=["Predicted: No IBD", "Predicted: IBD"])
    report = f"""# IBD risk model — training report

> **{DISCLAIMER}**
> All metrics below measure how well the model recovers the *synthetic generation formula*.
> They are **not** evidence of clinical or diagnostic accuracy.

## Data
- Source: `Saudi_IBD_Synthetic.xlsx`, sheet `Synthetic_Data` — {len(y)} rows, IBD prevalence {y.mean():.1%}
- Features: **61** (README Option A minus `oral_contraceptive_use`). Excluded: {", ".join(f"`{c}`" for c in EXCLUDED)}
- Split: stratified 80/20 (train {len(y_tr)}, test {len(y_te)}), seed {SEED}
- Model comparison: nested 5-fold CV on the training set (hyperparameters tuned inside each fold on PR-AUC)

## Model comparison (out-of-fold, training set)
Precision / recall / accuracy are at each model's own threshold (max F1 with recall ≥ {MIN_RECALL}).

{fmt(cmp)}

**Chosen model: {chosen}** — {reason}.
Final hyperparameters (tuned on all data): `{best_params}`

## Decision threshold
- Rule: maximize F1 subject to recall ≥ {MIN_RECALL} on out-of-fold training predictions → **{threshold:.3f}**
- Risk tiers on the predicted probability: Low < {TIERS['Low']} ≤ Moderate < {TIERS['Moderate']} ≤ High

### Precision at each recall level (out-of-fold, training set)
{fmt(par_oof)}

## Held-out test set ({len(y_te)} people, never used for training or tuning)
| Metric | Value |
|---|---|
| ROC-AUC (95% bootstrap CI) | {test['ROC_AUC']:.3f} ({lo:.3f}–{hi:.3f}) |
| PR-AUC | {test['PR_AUC']:.3f} |
| **Precision** (PPV) | **{test['precision']:.3f}** |
| **Recall** (sensitivity) | **{test['recall']:.3f}** |
| **Accuracy** | **{test['accuracy']:.3f}** |
| F1 | {test['f1']:.3f} |
| Specificity | {test['specificity']:.3f} |
| NPV | {test['npv']:.3f} |
| Brier score | {test['Brier']:.3f} |
| Calibration slope / intercept | {slope:.2f} / {intercept:.2f} |

{cm.to_markdown()}

### Precision at each recall level (test set)
{fmt(par_test)}

## Explainability (SHAP, final model)
Importance by input group (sum of mean |SHAP|):

{fmt(gi)}

Top 10 features: {", ".join(f"`{c}`" for c in mean_abs.head(10).index)}

### V6 sanity checks
- Excluded columns absent from the feature matrix: **yes** (asserted in code)
- Composites and components not mixed: **yes** (composites excluded, Option A)
- SHAP direction vs published evidence:

{pd.DataFrame(sign_rows).to_markdown(index=False)}

- Low-signal variables (README §9) — importance rank out of 61 (higher = less important):
  {", ".join(f"`{c}` #{r}" for c, r in sorted(low_rank.items(), key=lambda kv: kv[1]))}
- Never narrated in explanations (README §8): {", ".join(f"`{c}`" for c in ["appendectomy_history", "childhood_infection_count", "total_triglycerides_mg_dL", "palmitic_acid_ug_mL"])}

## Files
- `model.joblib` — final model (refit on all {len(y)} rows), threshold, tiers, feature order, defaults
- `roc_pr.png`, `calibration.png`, `shap_summary.png`

_Training time: {time.time() - t0:.0f}s_
"""
    (OUT / "model_report.md").write_text(report)
    print(f"\nSaved to {OUT}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

"""SHAP explanations (in log-odds units) for whichever model train.py selects."""
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features import NO_NARRATE, decode_value


def make_explainer(model, background):
    """Return f(X: DataFrame) -> ndarray (n_rows, n_features) of SHAP values in log-odds."""
    bg = background.sample(min(len(background), 200), random_state=0)

    # Scaler + logistic regression: exact linear SHAP, coef * (x - mean(background)).
    if isinstance(model, Pipeline) and len(model.steps) == 2 \
            and isinstance(model[0], StandardScaler) and isinstance(model[-1], LogisticRegression):
        w = model[-1].coef_[0] / model[0].scale_
        mu = bg.mean().values
        return lambda X: (np.asarray(X, dtype=float) - mu) * w

    if isinstance(model, (HistGradientBoostingClassifier, RandomForestClassifier)):
        tree = shap.TreeExplainer(model, bg, model_output="raw" if isinstance(model, HistGradientBoostingClassifier)
                                  else "probability")

        def f(X):
            v = tree.shap_values(X, check_additivity=False)
            v = np.asarray(v)
            return v[..., 1] if v.ndim == 3 else v
        return f

    # Anything else (spline pipeline, ensemble): model-agnostic permutation SHAP on log-odds.
    def logit(X):
        p = np.clip(model.predict_proba(pd.DataFrame(X, columns=bg.columns))[:, 1], 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p))
    perm = shap.PermutationExplainer(logit, shap.maskers.Independent(bg, max_samples=100))
    return lambda X: perm(X, silent=True).values


def top_factors(shap_row, x_row, k=5):
    """Top-k contributions for one patient, skipping variables README §8 forbids narrating."""
    s = pd.Series(shap_row, index=x_row.index)
    s = s.drop(NO_NARRATE, errors="ignore")
    s = s.reindex(s.abs().sort_values(ascending=False).index)[:k]
    return [{"variable": c, "value": decode_value(c, x_row[c]),
             "effect": "raises risk" if v > 0 else "lowers risk", "shap_log_odds": round(float(v), 3)}
            for c, v in s.items()]

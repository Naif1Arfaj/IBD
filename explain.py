"""SHAP explanations (in log-odds units) for whichever model train.py selects."""
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURES, NO_NARRATE, by_feature, feature_value


def make_explainer(model, background):
    """Return f(X: DataFrame) -> ndarray (n_rows, n_model_columns) of SHAP values in log-odds.

    A leading SimpleImputer is applied first, so SHAP describes the values the model actually used
    (a blank input contributes as its imputed, typical value).
    """
    bg = background.sample(min(len(background), 200), random_state=0)
    core, impute = model, (lambda X: X)
    if isinstance(model, Pipeline) and isinstance(model[0], SimpleImputer):
        imputer = model[0]
        impute = lambda X: pd.DataFrame(np.asarray(imputer.transform(X), dtype=float),  # noqa: E731
                                        columns=bg.columns)
        core = model[1:] if len(model.steps) > 2 else model[-1]
    bg_used = impute(bg)

    # Scaler + logistic regression: exact linear SHAP, coef * (x - mean(background)).
    if isinstance(core, Pipeline) and len(core.steps) == 2 \
            and isinstance(core[0], StandardScaler) and isinstance(core[-1], LogisticRegression):
        w = core[-1].coef_[0] / core[0].scale_
        mu = bg_used.mean().values
        return lambda X: (np.asarray(impute(X), dtype=float) - mu) * w

    if isinstance(core, (HistGradientBoostingClassifier, RandomForestClassifier)):
        tree = shap.TreeExplainer(core, bg_used, model_output="raw" if isinstance(core, HistGradientBoostingClassifier)
                                  else "probability")

        def f(X):
            v = tree.shap_values(impute(X), check_additivity=False)
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
    """Top-k contributions per input for one patient, skipping variables README §8 forbids narrating.

    `x_row` is one encoded model row; a one-hot input's columns are summed back into that input.
    """
    s = pd.Series(by_feature(shap_row), index=FEATURES)
    s = s.drop(NO_NARRATE, errors="ignore")
    s = s.reindex(s.abs().sort_values(ascending=False).index)[:k]
    return [{"variable": c, "value": feature_value(c, x_row),
             "effect": "raises risk" if v > 0 else "lowers risk", "shap_log_odds": round(float(v), 3)}
            for c, v in s.items()]

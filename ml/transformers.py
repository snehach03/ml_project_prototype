"""Custom scikit-learn transformers (kept in their own module so saved models unpickle anywhere)."""

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class Winsorizer(BaseEstimator, TransformerMixin):
    """Clip every feature to the [lower, upper] percentiles learned on training data."""

    def __init__(self, lower=1.0, upper=99.0):
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        self.low_ = np.nanpercentile(values, self.lower, axis=0)
        self.high_ = np.nanpercentile(values, self.upper, axis=0)
        return self

    def transform(self, X):
        values = np.asarray(X, dtype=float)
        return np.clip(values, self.low_, self.high_)

# -*- coding: utf-8 -*-
"""
ensemble_model.py — Class WeightedEnsemble
File ini TERPISAH dari qgis agar bisa diimport dari Jupyter Notebook
maupun dari plugin QGIS.
"""

import numpy as np


class WeightedEnsemble:
    """
    Ensemble LGBM + RF + XGB dengan bobot F1-score.
    Kompatibel dengan Jupyter Notebook dan plugin QGIS.
    """

    def __init__(self, models: dict, weights: dict, metadata: dict):
        self.models         = models
        self.weights        = weights
        self.meta           = metadata
        self.n_features_in_ = metadata.get('n_features', 9)
        self.classes_       = np.array([1, 2, 3])
        self.feature_names_ = metadata.get('feature_names', [])

    def predict_proba(self, X):
        proba = np.zeros((X.shape[0], len(self.classes_)))
        for name, model in self.models.items():
            proba += self.weights[name] * model.predict_proba(X)
        return proba

    def predict(self, X):
        indices = np.argmax(self.predict_proba(X), axis=1)
        return self.classes_[indices]

    def __repr__(self):
        w = self.weights
        return (
            f"WeightedEnsemble(\n"
            f"  RF={w.get('rf',0):.6f}, "
            f"LGBM={w.get('lgbm',0):.6f}, "
            f"XGB={w.get('xgb',0):.6f}\n"
            f"  features={self.n_features_in_}, "
            f"classes={list(self.classes_)}\n"
            f")"
        )

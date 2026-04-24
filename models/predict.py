import os
import pickle
import numpy as np
import pandas as pd

MODEL_PATH    = os.path.join(os.path.dirname(__file__), "model.pkl")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "feature_cols.pkl")


def load_model():
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(FEATURES_PATH, "rb") as f:
        feature_cols = pickle.load(f)
    print(f"[predict] Model loaded. Features: {len(feature_cols)}")
    return model, feature_cols


def predict(model, feature_cols: list, df: pd.DataFrame) -> pd.Series:
    """
    Generate raw predictions for the given dataframe.
    Only uses columns the model was trained on.
    """
    available = [c for c in feature_cols if c in df.columns]
    missing   = [c for c in feature_cols if c not in df.columns]

    if missing:
        print(f"[predict] Warning – {len(missing)} feature(s) missing, filling with 0: {missing}")

    X = df.reindex(columns=feature_cols, fill_value=0)
    preds = model.predict(X)
    preds = np.clip(preds, 0, None)
    return pd.Series(preds, index=df.index, name="predicted_units")
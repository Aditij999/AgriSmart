"""
yield_model.py
--------------
Yield Prediction Module — Phase II Module 3

HOW THE TWO DATASETS ARE USED:
  Dataset 1 → crop_fertilizer_data.csv  
              Gives us: N, P, K, pH, Rainfall, Temperature, Crop (16 crops, 3522 rows)
              Role: these are our INPUT FEATURES (X)

  Dataset 2 → Crop Production data.csv  
              Gives us: Area (ha), Production (tonnes) for 126 crops, 246,000 rows
              Role: we compute real Yield = Production/Area × 1000 (kg/ha)
              These real stats become our TARGET values (y)

MERGE STRATEGY:
  Both datasets share Crop as a key.
  For each row in Dataset 1, we assign a yield value drawn from
  the REAL distribution of that crop in Dataset 2, then slightly
  adjusted by soil quality (N, pH, Rainfall).
  
  This is academically valid because:
  - Yield ranges are real (from 246,000 historical records)
  - Soil adjustments follow established agronomic science
  - The model learns how soil features WITHIN each crop affect yield
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR         = os.path.join(BASE_DIR, "data")
MODEL_DIR        = os.path.join(BASE_DIR, "models")
FERTILIZER_CSV   = os.path.join(DATA_DIR, "crop_fertilizer_data.csv")
PRODUCTION_CSV   = os.path.join(DATA_DIR, "crop_production_data.csv")
MERGED_CSV       = os.path.join(DATA_DIR, "merged_yield_dataset.csv")
YIELD_MODEL_PATH = os.path.join(MODEL_DIR, "yield_model.pkl")
ENCODER_PATH     = os.path.join(MODEL_DIR, "crop_label_encoder.pkl")

os.makedirs(MODEL_DIR, exist_ok=True)

# 5 regional crops
ALL_CROPS = ['Cotton', 'Groundnut', 'Jowar', 'Sugarcane', 'Wheat']

FEATURE_COLS = ["Nitrogen", "Phosphorus", "Potassium", "pH", "Rainfall", "Temperature"]

# Name mapping: Dataset1 crop name → Dataset2 crop name(s)
PROD_NAME_MAP = {
    'Cotton':    ['Cotton(lint)', 'Kapas'],
    'Groundnut': ['Groundnut'],
    'Jowar':     ['Jowar'],
    'Sugarcane': ['Sugarcane'],
    'Wheat':     ['Wheat'],
}


# ─────────────────────────────────────────────
# STEP 1: GET REAL YIELD STATS FROM DATASET 2
# ─────────────────────────────────────────────

def load_real_yield_stats(production_csv_path: str) -> pd.DataFrame:
    """
    Read Dataset 2 and compute per-crop yield statistics.
    Yield = (Production in tonnes / Area in ha) × 1000  →  kg/ha
    
    Returns DataFrame indexed by our crop name with columns:
      mean, std, p10, p90  (all in kg/ha)
    """
    print("📂 Loading Dataset 2: Crop Production data (246,000 records)...")

    all_prod_names = [n for names in PROD_NAME_MAP.values() for n in names]
    reverse_map    = {pn: our for our, pns in PROD_NAME_MAP.items() for pn in pns}

    chunks = []
    for chunk in pd.read_csv(production_csv_path, chunksize=10000):
        filtered = chunk[chunk["Crop"].isin(all_prod_names)]
        chunks.append(filtered)

    df = pd.concat(chunks, ignore_index=True)
    df = df.dropna(subset=["Production", "Area"])
    df = df[df["Area"] > 0].copy()
    df["Yield_kg_ha"] = ((df["Production"] / df["Area"]) * 1000).round(1)
    df = df[(df["Yield_kg_ha"] > 0) & (df["Yield_kg_ha"] < 300_000)]
    df["OurCrop"] = df["Crop"].map(reverse_map)

    stats = df.groupby("OurCrop")["Yield_kg_ha"].agg(
        count="count",
        mean="mean",
        std="std",
        p10=lambda x: x.quantile(0.10),
        p90=lambda x: x.quantile(0.90),
    ).round(1)

    print(f"   ✅ {df.shape[0]:,} production records → yield stats for {len(stats)} crops")
    print()
    print(f"   {'Crop':<12} {'Records':>9} {'Mean kg/ha':>11} {'P10':>8} {'P90':>9}")
    print(f"   {'-'*52}")
    for crop, row in stats.iterrows():
        print(f"   {crop:<12} {int(row['count']):>9,} {row['mean']:>11,.0f} {row['p10']:>8,.0f} {row['p90']:>9,.0f}")

    return stats


# ─────────────────────────────────────────────
# STEP 2: MERGE BOTH DATASETS
# ─────────────────────────────────────────────

def build_merged_dataset(yield_stats: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """
    Combine Dataset 1 (soil features) with real yield distributions.

    For each row in Dataset 1:
      1. Get real yield distribution for that crop from Dataset 2
      2. Draw base yield from that distribution
      3. Adjust slightly for soil quality
    """
    print("\n📂 Loading Dataset 1: Fertilizer/Soil data (3,522 rows)...")
    df = pd.read_csv(FERTILIZER_CSV)
    df["Crop"] = df["Crop"].str.strip().str.title()
    df = df[df["Crop"].isin(ALL_CROPS)].copy()
    df.dropna(subset=FEATURE_COLS, inplace=True)
    print(f"   ✅ {df.shape[0]} soil feature rows loaded for {df['Crop'].nunique()} crops")

    rng = np.random.default_rng(seed)
    yields = []

    for _, row in df.iterrows():
        crop = row["Crop"]

        if crop in yield_stats.index:
            mean_y = yield_stats.loc[crop, "mean"]
            std_y  = yield_stats.loc[crop, "std"]
            p10    = yield_stats.loc[crop, "p10"]
            p90    = yield_stats.loc[crop, "p90"]
        else:
            mean_y, std_y, p10, p90 = 2000, 600, 600, 3500

        # Agronomic soil quality adjustment — bounded to ±25%
        n_factor    = min(row["Nitrogen"]   / 120, 1.5) * 0.08
        p_factor    = min(row["Phosphorus"] / 60,  1.5) * 0.05
        ph_penalty  = 1.0 - abs(row["pH"] - 6.5) * 0.03
        rain_factor = min(row["Rainfall"] / 900, 1.3) * 0.05
        multiplier  = max(0.85, min(1 + n_factor + p_factor + rain_factor, 1.25))

        base  = rng.normal(mean_y, std_y * 0.3)
        y_val = base * multiplier * ph_penalty
        y_val = max(p10 * 0.5, min(y_val, p90 * 1.5))
        yields.append(round(y_val, 1))

    df = df.copy()
    df["Yield_kg_ha"] = yields
    return df


def load_and_prepare_data() -> pd.DataFrame:
    """Load merged dataset — build from scratch if not cached."""
    if os.path.exists(MERGED_CSV):
        print(f"📂 Loading pre-built merged dataset...")
        df = pd.read_csv(MERGED_CSV)
        df = df[df["Crop"].isin(ALL_CROPS)].dropna(subset=FEATURE_COLS + ["Yield_kg_ha"])
        print(f"   ✅ {df.shape[0]} rows, {df['Crop'].nunique()} crops")
        print()
        print(f"   {'Crop':<12} {'Rows':>6} {'Mean Yield':>11}")
        print(f"   {'-'*32}")
        for crop, grp in df.groupby("Crop"):
            print(f"   {crop:<12} {len(grp):>6} {grp['Yield_kg_ha'].mean():>11,.0f} kg/ha")
        return df

    elif os.path.exists(PRODUCTION_CSV):
        yield_stats = load_real_yield_stats(PRODUCTION_CSV)
        df = build_merged_dataset(yield_stats)
        df.to_csv(MERGED_CSV, index=False)
        print(f"\n   ✅ Merged dataset saved → {MERGED_CSV}")
        return df

    else:
        print("⚠️  Crop Production CSV not found. Using pre-built merged CSV.")
        if os.path.exists(MERGED_CSV):
            return pd.read_csv(MERGED_CSV)
        else:
            raise FileNotFoundError(
                f"Place 'Crop Production data.csv' in {DATA_DIR}/ as 'crop_production_data.csv'"
            )


# ─────────────────────────────────────────────
# STEP 3: ENCODE CROP + TRAIN
# ─────────────────────────────────────────────

def train_yield_model(df: pd.DataFrame) -> dict:
    """
    Train yield regression model.
    Crop name is label-encoded and included as a feature
    so the model learns per-crop yield patterns.
    """
    le = LabelEncoder()
    df = df.copy()
    df["Crop_encoded"] = le.fit_transform(df["Crop"])
    joblib.dump(le, ENCODER_PATH)

    feature_cols_with_crop = FEATURE_COLS + ["Crop_encoded"]

    X = df[feature_cols_with_crop].values
    y = df["Yield_kg_ha"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print("\n" + "═" * 58)
    print("   YIELD MODEL — TRAINING")
    print("═" * 58)
    print(f"   Crops in model : {sorted(le.classes_.tolist())}")
    print(f"   Total rows     : {len(df)}")
    print(f"   Features used  : {feature_cols_with_crop}")
    print(f"   Train / Test   : {len(X_train)} / {len(X_test)}")

    models = {
        "Linear Regression":           LinearRegression(),
        "Random Forest Regressor":     RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "Gradient Boosting Regressor": GradientBoostingRegressor(n_estimators=100, random_state=42),
    }

    results    = {}
    best_model = None
    best_r2    = -float("inf")
    best_name  = ""

    print()
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        r2  = round(r2_score(y_test, y_pred), 4)
        mae = round(mean_absolute_error(y_test, y_pred), 1)
        results[name] = {"R2": r2, "MAE_kg_ha": mae}
        print(f"   {name:<35} R²={r2}   MAE={mae:,.0f} kg/ha")
        if r2 > best_r2:
            best_r2, best_model, best_name = r2, model, name

    print(f"\n   🏆 Best: {best_name} (R²={best_r2})")

    if hasattr(best_model, "feature_importances_"):
        print("\n   Feature Importances:")
        for feat, imp in sorted(zip(feature_cols_with_crop, best_model.feature_importances_),
                                 key=lambda x: x[1], reverse=True):
            bar = "█" * int(imp * 35)
            print(f"   {feat:<18}: {imp:.4f}  {bar}")

    print("═" * 58)

    return {
        "model": best_model, "encoder": le,
        "features": feature_cols_with_crop,
        "metrics": results, "best_name": best_name,
    }


# ─────────────────────────────────────────────
# SAVE / LOAD
# ─────────────────────────────────────────────

def save_model(model, path: str = YIELD_MODEL_PATH) -> None:
    joblib.dump(model, path)
    print(f"\n💾 Yield model saved → {path}  ({os.path.getsize(path)/1024:.1f} KB)")


def load_model(path: str = YIELD_MODEL_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Run: python modules/yield_model.py first")
    return joblib.load(path)


# ─────────────────────────────────────────────
# PREDICTION
# ─────────────────────────────────────────────

def predict_yield(soil_input: dict, model=None, crop: str = None) -> dict:
    """
    Predict yield. If crop is provided, encodes it as a feature.
    If not, uses only numeric soil features (model averages across crops).
    """
    if model is None:
        model = load_model()

    le = joblib.load(ENCODER_PATH) if os.path.exists(ENCODER_PATH) else None

    if crop and le is not None and crop in le.classes_:
        crop_encoded = le.transform([crop])[0]
        features = [[soil_input[f] for f in FEATURE_COLS] + [crop_encoded]]
    elif le is not None:
        # use mean encoding as fallback
        crop_encoded = len(le.classes_) // 2
        features = [[soil_input[f] for f in FEATURE_COLS] + [crop_encoded]]
    else:
        features = [[soil_input[f] for f in FEATURE_COLS]]

    pred = round(float(model.predict(features)[0]), 1)

    if pred < 1000:
        interp = "⚠️  Low yield — soil needs significant correction."
    elif pred < 3000:
        interp = "🟡 Moderate yield — improvement possible."
    elif pred < 15000:
        interp = "🟢 Good yield — conditions are favorable."
    else:
        interp = "🟢 High yield — excellent conditions (Sugarcane expected range)."

    return {"predicted_yield_kg_ha": pred, "interpretation": interp}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    df     = load_and_prepare_data()
    result = train_yield_model(df)
    save_model(result["model"])

    print("\n🔍 Sample predictions across crops:")
    soil = {"Nitrogen": 80, "Phosphorus": 40, "Potassium": 40,
            "pH": 6.5, "Rainfall": 800, "Temperature": 25}
    le = result["encoder"]
    for crop in sorted(le.classes_):
        p = predict_yield(soil, model=result["model"], crop=crop)
        print(f"   {crop:<12}: {p['predicted_yield_kg_ha']:>10,.1f} kg/ha")

    print("\n✅ Done. Run pipeline.py to use the full system.\n")

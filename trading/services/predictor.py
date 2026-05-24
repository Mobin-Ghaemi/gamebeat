import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import warnings

warnings.filterwarnings('ignore')

FEATURE_COLS = [
    'rsi', 'rsi_fast',
    'macd', 'macd_signal', 'macd_hist',
    'bb_position',
    'ema9', 'ema21', 'ema50',
    'vol_ratio',
    'price_change_1', 'price_change_3', 'price_change_5',
    'stoch_k', 'stoch_d',
    'atr',
]


def _normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize price-based features relative to current price."""
    df = df.copy()
    price = df['close']
    for col in ['ema9', 'ema21', 'ema50', 'macd', 'macd_signal', 'macd_hist', 'atr']:
        if col in df.columns:
            df[col] = df[col] / price
    return df


def _build_target(df: pd.DataFrame, horizon: int = 1) -> pd.Series:
    """1 = price goes UP in `horizon` candles, 0 = DOWN."""
    future_close = df['close'].shift(-horizon)
    return (future_close > df['close']).astype(int)


def train_and_predict(df: pd.DataFrame) -> dict:
    """
    Train an ensemble model on historical candles and predict next candle direction.
    Returns prediction dict with direction, confidence, and model agreement score.
    """
    df_norm = _normalize_features(df)

    available_features = [c for c in FEATURE_COLS if c in df_norm.columns]
    X_raw = df_norm[available_features].copy()
    y = _build_target(df_norm, horizon=1)

    # Remove rows with NaN or where target is unknown (last row)
    valid_mask = X_raw.notna().all(axis=1) & y.notna()
    X_clean = X_raw[valid_mask]
    y_clean = y[valid_mask]

    if len(X_clean) < 30:
        return {'direction': 'NEUTRAL', 'confidence': 50.0, 'model_agreement': 0.0}

    # Train on all valid rows
    X_train = X_clean
    y_train = y_clean

    # Predict for the last available row (most recent candle)
    X_pred = X_raw.iloc[[-1]].fillna(X_raw.median())

    # Ensemble of two models
    rf = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ))
    ])

    gb = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', GradientBoostingClassifier(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.05,
            random_state=42,
        ))
    ])

    rf.fit(X_train, y_train)
    gb.fit(X_train, y_train)

    rf_prob = rf.predict_proba(X_pred)[0]
    gb_prob = gb.predict_proba(X_pred)[0]

    # Weighted average (RF slightly more weight)
    avg_prob = 0.55 * rf_prob + 0.45 * gb_prob
    pred_class = int(np.argmax(avg_prob))
    confidence = float(avg_prob[pred_class]) * 100

    # Model agreement: both agree = high agreement
    rf_class = int(np.argmax(rf_prob))
    gb_class = int(np.argmax(gb_prob))
    agreement = 1.0 if rf_class == gb_class else abs(rf_prob[1] - gb_prob[1])

    direction = 'UP' if pred_class == 1 else 'DOWN'

    # Feature importance (from RF)
    feature_names = available_features
    importances = rf.named_steps['clf'].feature_importances_
    top_features = sorted(
        zip(feature_names, importances.tolist()),
        key=lambda x: x[1], reverse=True
    )[:5]

    return {
        'direction': direction,
        'confidence': round(confidence, 1),
        'model_agreement': round(float(agreement), 2),
        'rf_confidence': round(float(rf_prob[pred_class]) * 100, 1),
        'gb_confidence': round(float(gb_prob[pred_class]) * 100, 1),
        'top_features': [{'name': n, 'importance': round(v * 100, 1)} for n, v in top_features],
        'training_samples': int(len(X_train)),
    }


def combine_predictions(ml_result: dict, tech_result: dict) -> dict:
    """Merge ML prediction with technical analysis for final signal."""
    ml_dir = ml_result['direction']
    tech_dir = tech_result['direction']

    ml_conf = ml_result['confidence']
    tech_conf = tech_result['confidence']

    # Agreement bonus
    if ml_dir == tech_dir and ml_dir != 'NEUTRAL':
        direction = ml_dir
        combined_conf = min(98, 0.5 * ml_conf + 0.5 * tech_conf + 8)
        agreement = 'HIGH'
    elif ml_dir == 'NEUTRAL':
        direction = tech_dir
        combined_conf = tech_conf * 0.85
        agreement = 'MEDIUM'
    elif tech_dir == 'NEUTRAL':
        direction = ml_dir
        combined_conf = ml_conf * 0.85
        agreement = 'MEDIUM'
    else:
        # Disagreement: use whichever has higher confidence
        if ml_conf >= tech_conf:
            direction = ml_dir
            combined_conf = ml_conf * 0.75
        else:
            direction = tech_dir
            combined_conf = tech_conf * 0.75
        agreement = 'LOW'

    return {
        'direction': direction,
        'confidence': round(combined_conf, 1),
        'agreement': agreement,
    }

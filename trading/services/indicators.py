import pandas as pd
import numpy as np


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to the OHLCV dataframe."""
    df = df.copy()
    close = df['close']
    volume = df['volume']

    # Trend
    df['ema9'] = close.ewm(span=9, adjust=False).mean()
    df['ema21'] = close.ewm(span=21, adjust=False).mean()
    df['ema50'] = close.ewm(span=50, adjust=False).mean()
    df['sma200'] = close.rolling(200).mean()

    # Momentum
    df['rsi'] = calculate_rsi(close, 14)
    df['rsi_fast'] = calculate_rsi(close, 7)
    df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(close)

    # Volatility
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = calculate_bollinger(close)
    bb_range = (df['bb_upper'] - df['bb_lower']).replace(0, np.nan)
    df['bb_position'] = (close - df['bb_lower']) / bb_range  # 0=lower, 1=upper

    # Volume
    df['vol_sma20'] = volume.rolling(20).mean()
    df['vol_ratio'] = volume / df['vol_sma20'].replace(0, np.nan)

    # Price dynamics
    df['price_change_1'] = close.pct_change(1)
    df['price_change_3'] = close.pct_change(3)
    df['price_change_5'] = close.pct_change(5)

    # ATR (Average True Range)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - close.shift()).abs(),
        (df['low'] - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # Stochastic
    low14 = df['low'].rolling(14).min()
    high14 = df['high'].rolling(14).max()
    stoch_range = (high14 - low14).replace(0, np.nan)
    df['stoch_k'] = 100 * (close - low14) / stoch_range
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    return df.dropna(subset=['rsi', 'macd', 'bb_position'])


def get_technical_signals(df: pd.DataFrame) -> dict:
    """Generate buy/sell signals from the latest indicator values."""
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    signals = []

    # RSI signals
    rsi = last['rsi']
    if rsi < 30:
        signals.append(('RSI', 'UP', 0.8, f"RSI در ناحیه اشباع فروش ({rsi:.1f})"))
    elif rsi > 70:
        signals.append(('RSI', 'DOWN', 0.8, f"RSI در ناحیه اشباع خرید ({rsi:.1f})"))
    elif rsi < 45:
        signals.append(('RSI', 'UP', 0.5, f"RSI زیر میانه ({rsi:.1f})"))
    elif rsi > 55:
        signals.append(('RSI', 'DOWN', 0.5, f"RSI بالای میانه ({rsi:.1f})"))

    # MACD signals
    if last['macd_hist'] > 0 and prev['macd_hist'] <= 0:
        signals.append(('MACD', 'UP', 0.85, "تقاطع صعودی MACD"))
    elif last['macd_hist'] < 0 and prev['macd_hist'] >= 0:
        signals.append(('MACD', 'DOWN', 0.85, "تقاطع نزولی MACD"))
    elif last['macd'] > last['macd_signal']:
        signals.append(('MACD', 'UP', 0.55, "MACD بالای خط سیگنال"))
    else:
        signals.append(('MACD', 'DOWN', 0.55, "MACD زیر خط سیگنال"))

    # Bollinger Band signals
    bb_pos = last['bb_position']
    if bb_pos < 0.1:
        signals.append(('BB', 'UP', 0.75, "قیمت نزدیک باند پایین"))
    elif bb_pos > 0.9:
        signals.append(('BB', 'DOWN', 0.75, "قیمت نزدیک باند بالا"))

    # EMA trend
    if last['ema9'] > last['ema21'] > last['ema50']:
        signals.append(('EMA', 'UP', 0.7, "ترتیب EMA صعودی"))
    elif last['ema9'] < last['ema21'] < last['ema50']:
        signals.append(('EMA', 'DOWN', 0.7, "ترتیب EMA نزولی"))

    # Volume confirmation
    vol_ratio = last.get('vol_ratio', 1)
    vol_note = f"حجم {vol_ratio:.1f}x میانگین"

    # Stochastic
    stoch = last.get('stoch_k', 50)
    if stoch < 20:
        signals.append(('Stoch', 'UP', 0.65, f"استوکاستیک اشباع فروش ({stoch:.0f})"))
    elif stoch > 80:
        signals.append(('Stoch', 'DOWN', 0.65, f"استوکاستیک اشباع خرید ({stoch:.0f})"))

    # Compute weighted direction
    up_score = sum(w for _, d, w, _ in signals if d == 'UP')
    down_score = sum(w for _, d, w, _ in signals if d == 'DOWN')
    total = up_score + down_score

    if total == 0:
        direction = 'NEUTRAL'
        confidence = 50.0
    elif up_score > down_score:
        direction = 'UP'
        confidence = round((up_score / total) * 100, 1)
    else:
        direction = 'DOWN'
        confidence = round((down_score / total) * 100, 1)

    return {
        'direction': direction,
        'confidence': confidence,
        'signals': [{'name': n, 'dir': d, 'weight': w, 'note': note} for n, d, w, note in signals],
        'rsi': round(float(rsi), 2),
        'macd': round(float(last['macd']), 6),
        'macd_signal': round(float(last['macd_signal']), 6),
        'macd_hist': round(float(last['macd_hist']), 6),
        'bb_position': round(float(bb_pos), 3),
        'bb_upper': round(float(last['bb_upper']), 6),
        'bb_lower': round(float(last['bb_lower']), 6),
        'ema9': round(float(last['ema9']), 6),
        'ema21': round(float(last['ema21']), 6),
        'ema50': round(float(last['ema50']), 6),
        'vol_ratio': round(float(vol_ratio), 2),
        'stoch_k': round(float(last.get('stoch_k', 50)), 1),
        'vol_note': vol_note,
    }

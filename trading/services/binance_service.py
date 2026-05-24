import re
import requests
import pandas as pd
from urllib.parse import urlparse, unquote

BINANCE_BASE = "https://api.binance.com/api/v3"

INTERVAL_MAP = {
    '5m': '5m',
    '30m': '30m',
    '1h': '1h',
    '4h': '4h',
    '1d': '1d',
}


def parse_symbol_from_input(user_input: str) -> str:
    """Extract trading symbol from Binance URL or raw symbol string."""
    text = user_input.strip().upper()

    # Direct symbol like BTCUSDT, BTC/USDT, BTC-USDT
    if re.match(r'^[A-Z]{2,10}[-/]?[A-Z]{2,10}$', text):
        return re.sub(r'[-/]', '', text)

    # TradingView URL: tradingview.com/chart/...?symbol=BINANCE:BTCUSDT
    tv_match = re.search(r'symbol=(?:BINANCE[:%3A])?([A-Z]{4,20})', text, re.IGNORECASE)
    if tv_match:
        return tv_match.group(1).upper()

    # Binance URL: binance.com/en/trade/BTC_USDT or /BTC/USDT
    binance_match = re.search(
        r'(?:trade|futures|delivery)/([A-Z]{2,10})[_/]([A-Z]{2,10})',
        text, re.IGNORECASE
    )
    if binance_match:
        return (binance_match.group(1) + binance_match.group(2)).upper()

    # Fallback: grab two consecutive uppercase tokens
    tokens = re.findall(r'[A-Z]{2,10}', text)
    if len(tokens) >= 2:
        return tokens[0] + tokens[1]

    if tokens:
        return tokens[0] + 'USDT'

    raise ValueError(f"نمیتونم نماد رو از '{user_input}' استخراج کنم")


def fetch_klines(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    """Fetch OHLCV candlestick data from Binance public API."""
    url = f"{BINANCE_BASE}/klines"
    params = {
        'symbol': symbol.upper(),
        'interval': INTERVAL_MAP.get(interval, interval),
        'limit': min(limit, 1000),
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    if not raw:
        raise ValueError(f"داده‌ای برای نماد {symbol} پیدا نشد")

    df = pd.DataFrame(raw, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    df = df.set_index('open_time')

    return df[['open', 'high', 'low', 'close', 'volume']]


def get_ticker_price(symbol: str) -> float:
    """Get current spot price for a symbol."""
    url = f"{BINANCE_BASE}/ticker/price"
    resp = requests.get(url, params={'symbol': symbol.upper()}, timeout=5)
    resp.raise_for_status()
    return float(resp.json()['price'])


def validate_symbol(symbol: str) -> bool:
    """Check if symbol exists on Binance."""
    try:
        get_ticker_price(symbol)
        return True
    except Exception:
        return False

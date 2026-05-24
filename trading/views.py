import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import PredictionRecord
from .services.binance_service import parse_symbol_from_input, fetch_klines, get_ticker_price, validate_symbol
from .services.indicators import calculate_indicators, get_technical_signals
from .services.predictor import train_and_predict, combine_predictions

INTERVALS = [
    {'value': '5m', 'label': '5 دقیقه', 'icon': '⚡'},
    {'value': '30m', 'label': '30 دقیقه', 'icon': '🕐'},
    {'value': '1h', 'label': '1 ساعت', 'icon': '📊'},
    {'value': '4h', 'label': '4 ساعت', 'icon': '📈'},
    {'value': '1d', 'label': '1 روز', 'icon': '📅'},
]

POPULAR_SYMBOLS = [
    {'symbol': 'BTCUSDT', 'name': 'Bitcoin'},
    {'symbol': 'ETHUSDT', 'name': 'Ethereum'},
    {'symbol': 'BNBUSDT', 'name': 'Binance Coin'},
    {'symbol': 'SOLUSDT', 'name': 'Solana'},
    {'symbol': 'XRPUSDT', 'name': 'XRP'},
    {'symbol': 'ADAUSDT', 'name': 'Cardano'},
    {'symbol': 'DOGEUSDT', 'name': 'Dogecoin'},
    {'symbol': 'DOTUSDT', 'name': 'Polkadot'},
]


def index(request):
    recent = PredictionRecord.objects.all()[:10]
    return render(request, 'trading/index.html', {
        'intervals': INTERVALS,
        'popular_symbols': POPULAR_SYMBOLS,
        'recent_predictions': recent,
    })


@csrf_exempt
@require_POST
def analyze(request):
    try:
        data = json.loads(request.body)
        raw_input = data.get('symbol', '').strip()
        interval = data.get('interval', '1h')

        if not raw_input:
            return JsonResponse({'error': 'نماد ارز را وارد کنید'}, status=400)

        # Parse symbol
        try:
            symbol = parse_symbol_from_input(raw_input)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

        # Validate
        if not validate_symbol(symbol):
            return JsonResponse({'error': f"نماد '{symbol}' در Binance پیدا نشد"}, status=400)

        # Fetch data
        df = fetch_klines(symbol, interval, limit=300)
        if len(df) < 50:
            return JsonResponse({'error': 'داده کافی برای تحلیل وجود ندارد'}, status=400)

        current_price = get_ticker_price(symbol)

        # Calculate indicators
        df_with_ind = calculate_indicators(df)

        # Technical analysis
        tech_result = get_technical_signals(df_with_ind)

        # ML prediction
        ml_result = train_and_predict(df_with_ind)

        # Combined signal
        combined = combine_predictions(ml_result, tech_result)

        # Save to DB
        PredictionRecord.objects.create(
            symbol=symbol,
            interval=interval,
            prediction=combined['direction'],
            confidence=combined['confidence'],
            technical_signal=tech_result['direction'],
            ml_signal=ml_result['direction'],
            current_price=current_price,
            rsi=tech_result.get('rsi'),
            macd=tech_result.get('macd'),
        )

        # Prepare chart data (last 100 candles)
        chart_df = df_with_ind.tail(100)
        chart_data = {
            'labels': [str(t) for t in chart_df.index.strftime('%Y-%m-%d %H:%M')],
            'open': chart_df['open'].round(8).tolist(),
            'high': chart_df['high'].round(8).tolist(),
            'low': chart_df['low'].round(8).tolist(),
            'close': chart_df['close'].round(8).tolist(),
            'volume': chart_df['volume'].round(2).tolist(),
            'ema9': chart_df['ema9'].round(8).tolist(),
            'ema21': chart_df['ema21'].round(8).tolist(),
            'bb_upper': chart_df['bb_upper'].round(8).tolist(),
            'bb_mid': chart_df['bb_mid'].round(8).tolist(),
            'bb_lower': chart_df['bb_lower'].round(8).tolist(),
            'rsi': chart_df['rsi'].round(2).tolist(),
            'macd': chart_df['macd'].round(8).tolist(),
            'macd_signal': chart_df['macd_signal'].round(8).tolist(),
            'macd_hist': chart_df['macd_hist'].round(8).tolist(),
        }

        return JsonResponse({
            'symbol': symbol,
            'interval': interval,
            'current_price': current_price,
            'prediction': {
                'direction': combined['direction'],
                'confidence': combined['confidence'],
                'agreement': combined['agreement'],
            },
            'technical': {
                'direction': tech_result['direction'],
                'confidence': tech_result['confidence'],
                'signals': tech_result['signals'],
                'rsi': tech_result['rsi'],
                'macd': tech_result['macd'],
                'macd_hist': tech_result['macd_hist'],
                'bb_position': tech_result['bb_position'],
                'stoch_k': tech_result['stoch_k'],
                'vol_ratio': tech_result['vol_ratio'],
            },
            'ml': {
                'direction': ml_result['direction'],
                'confidence': ml_result['confidence'],
                'agreement': ml_result['model_agreement'],
                'top_features': ml_result.get('top_features', []),
                'training_samples': ml_result.get('training_samples', 0),
            },
            'chart': chart_data,
        })

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'اتصال به Binance قطع شد. دوباره تلاش کنید'}, status=503)
    except Exception as e:
        return JsonResponse({'error': f'خطا: {str(e)}'}, status=500)


def history(request):
    records = PredictionRecord.objects.all()[:50]
    return render(request, 'trading/history.html', {'records': records})

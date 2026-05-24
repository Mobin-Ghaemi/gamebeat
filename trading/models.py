from django.db import models


class PredictionRecord(models.Model):
    DIRECTION_CHOICES = [('UP', 'صعودی'), ('DOWN', 'نزولی'), ('NEUTRAL', 'خنثی')]
    INTERVAL_CHOICES = [('5m', '5 دقیقه'), ('30m', '30 دقیقه'), ('1h', '1 ساعت'), ('4h', '4 ساعت'), ('1d', '1 روز')]

    symbol = models.CharField(max_length=20)
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES)
    prediction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    confidence = models.FloatField()
    technical_signal = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    ml_signal = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    rsi = models.FloatField(null=True, blank=True)
    macd = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'پیش‌بینی'
        verbose_name_plural = 'پیش‌بینی‌ها'

    def __str__(self):
        return f"{self.symbol} {self.interval} → {self.prediction} ({self.confidence:.0f}%)"

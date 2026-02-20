from django.db import migrations, models


def set_sale_price(apps, schema_editor):
    Product = apps.get_model('gamenet', 'Product')
    for product in Product.objects.all():
        if not product.sale_price:
            product.sale_price = product.price
        product.save(update_fields=['sale_price'])


class Migration(migrations.Migration):

    dependencies = [
        ('gamenet', '0007_productcategory_image_alter_productcategory_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='purchase_price',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name='قیمت خرید (تومان)'),
        ),
        migrations.AddField(
            model_name='product',
            name='sale_price',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name='قیمت عرضه (تومان)'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='purchase_price',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name='قیمت خرید'),
        ),
        migrations.RunPython(set_sale_price, migrations.RunPython.noop),
    ]

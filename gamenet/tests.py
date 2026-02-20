import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Subscription
from gamenet.models import Device, Game, GameNet, Order, OrderItem, Product, ProductCategory, Session, Tournament


class BuffetAndProductManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='pass123456')
        self.client.force_login(self.user)

        self.gamenet = GameNet.objects.create(
            owner=self.user,
            name='Test GameNet',
            slug='test-gamenet',
        )

        Subscription.objects.create(
            user=self.user,
            service_type='gamenet',
            duration='1_month',
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
        )

    def test_quick_sell_success_decrements_stock_and_marks_unavailable(self):
        product = Product.objects.create(
            gamenet=self.gamenet,
            name='نوشابه',
            price=Decimal('10000'),
            sale_price=Decimal('12000'),
            purchase_price=Decimal('8000'),
            stock=5,
            is_available=True,
            is_active=True,
        )

        response = self.client.post(
            reverse('gamenet:quick_sell'),
            data=json.dumps({'items': [{'product_id': product.id, 'quantity': 5}]}),
            content_type='application/json',
        )
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)

        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertFalse(product.is_available)

    def test_quick_sell_insufficient_stock_rolls_back_order_and_stock(self):
        product = Product.objects.create(
            gamenet=self.gamenet,
            name='چیپس',
            price=Decimal('15000'),
            sale_price=Decimal('17000'),
            purchase_price=Decimal('11000'),
            stock=2,
            is_available=True,
            is_active=True,
        )

        response = self.client.post(
            reverse('gamenet:quick_sell'),
            data=json.dumps({'items': [{'product_id': product.id, 'quantity': 3}]}),
            content_type='application/json',
        )
        data = response.json()

        self.assertFalse(data['success'])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        product.refresh_from_db()
        self.assertEqual(product.stock, 2)

    def test_create_order_uses_atomic_stock_deduction(self):
        product = Product.objects.create(
            gamenet=self.gamenet,
            name='آب معدنی',
            price=Decimal('9000'),
            sale_price=Decimal('10000'),
            purchase_price=Decimal('7000'),
            stock=4,
            is_available=True,
            is_active=True,
        )

        response = self.client.post(
            reverse('gamenet:create_order'),
            data=json.dumps({'items': [{'product_id': product.id, 'quantity': 2}], 'customer_name': 'Ali'}),
            content_type='application/json',
        )
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(Order.objects.count(), 1)

        product.refresh_from_db()
        self.assertEqual(product.stock, 2)

    def test_end_session_with_order_rolls_back_session_and_device_on_stock_error(self):
        device = Device.objects.create(
            gamenet=self.gamenet,
            number=1,
            name='PS5-1',
            device_type='ps5',
            hourly_rate=Decimal('100000'),
            status='occupied',
        )
        session = Session.objects.create(
            device=device,
            customer_name='Customer',
            start_time=timezone.now() - timedelta(hours=2),
            hourly_rate=Decimal('100000'),
            is_active=True,
        )
        product = Product.objects.create(
            gamenet=self.gamenet,
            name='اسنک',
            price=Decimal('20000'),
            sale_price=Decimal('25000'),
            purchase_price=Decimal('14000'),
            stock=1,
            is_available=True,
            is_active=True,
        )

        response = self.client.post(
            reverse('gamenet:end_session_with_order', args=[session.id]),
            data=json.dumps({'items': [{'product_id': product.id, 'quantity': 2}]}),
            content_type='application/json',
        )
        data = response.json()

        self.assertFalse(data['success'])
        self.assertEqual(Order.objects.count(), 0)

        session.refresh_from_db()
        device.refresh_from_db()
        product.refresh_from_db()

        self.assertTrue(session.is_active)
        self.assertIsNone(session.end_time)
        self.assertEqual(device.status, 'occupied')
        self.assertEqual(product.stock, 1)

    def test_buffet_dashboard_shows_active_products_and_hides_create_link(self):
        category = ProductCategory.objects.create(
            gamenet=self.gamenet,
            name='نوشیدنی',
            icon='fas fa-glass-water',
            color='#3b82f6',
            is_active=True,
        )
        Product.objects.create(
            gamenet=self.gamenet,
            category=category,
            name='دوغ',
            price=Decimal('12000'),
            stock=0,
            is_available=False,
            is_active=True,
        )
        Product.objects.create(
            gamenet=self.gamenet,
            name='پفک',
            price=Decimal('11000'),
            stock=3,
            is_available=True,
            is_active=True,
        )
        Product.objects.create(
            gamenet=self.gamenet,
            category=category,
            name='INACTIVE',
            price=Decimal('1'),
            stock=10,
            is_available=True,
            is_active=False,
        )

        response = self.client.get(reverse('gamenet:buffet_dashboard'))

        self.assertContains(response, 'نوشیدنی')
        self.assertContains(response, 'دوغ')
        self.assertContains(response, 'پفک')
        self.assertNotContains(response, 'INACTIVE')
        self.assertContains(response, reverse('gamenet:product_list'))
        self.assertContains(response, reverse('gamenet:recent_sales_page'))
        self.assertNotContains(response, reverse('gamenet:product_create'))

    def test_product_page_has_modal_actions_and_category_redirects(self):
        category = ProductCategory.objects.create(
            gamenet=self.gamenet,
            name='خوراکی',
            icon='fas fa-cookie',
            color='#f59e0b',
        )

        response = self.client.get(reverse('gamenet:product_list'))
        self.assertContains(response, 'id="product-modal"', html=False)
        self.assertContains(response, 'id="category-modal"', html=False)
        self.assertContains(response, reverse('gamenet:category_create'))

        target = reverse('gamenet:product_list')
        list_redirect = self.client.get(reverse('gamenet:category_list'))
        self.assertEqual(list_redirect.status_code, 302)
        self.assertEqual(list_redirect['Location'], target)

        create_redirect = self.client.post(
            reverse('gamenet:category_create'),
            data={'name': 'نوشیدنی', 'icon': 'fas fa-glass-water', 'color': '#3b82f6', 'order': 1},
        )
        self.assertEqual(create_redirect.status_code, 302)
        self.assertEqual(create_redirect['Location'], target)

        edit_redirect = self.client.post(
            reverse('gamenet:category_edit', args=[category.id]),
            data={'name': 'خوراکی جدید', 'icon': 'fas fa-cookie', 'color': '#f59e0b', 'order': 2},
        )
        self.assertEqual(edit_redirect.status_code, 302)
        self.assertEqual(edit_redirect['Location'], target)

        delete_redirect = self.client.post(reverse('gamenet:category_delete', args=[category.id]))
        self.assertEqual(delete_redirect.status_code, 302)
        self.assertEqual(delete_redirect['Location'], target)

    def test_recent_sales_page_shows_item_rows_stats_and_per_page_pagination(self):
        p1 = Product.objects.create(
            gamenet=self.gamenet,
            name='نوشابه',
            price=Decimal('10000'),
            sale_price=Decimal('12000'),
            stock=20,
            is_active=True,
        )
        p2 = Product.objects.create(
            gamenet=self.gamenet,
            name='چیپس',
            price=Decimal('15000'),
            sale_price=Decimal('17000'),
            stock=20,
            is_active=True,
        )
        order = Order.objects.create(
            gamenet=self.gamenet,
            status='delivered',
            is_paid=True,
        )
        OrderItem.objects.create(
            order=order,
            product=p1,
            quantity=3,
            purchase_price=Decimal('7000'),
            unit_price=Decimal('12000'),
            total_price=Decimal('36000'),
        )
        OrderItem.objects.create(
            order=order,
            product=p2,
            quantity=1,
            purchase_price=Decimal('9000'),
            unit_price=Decimal('17000'),
            total_price=Decimal('17000'),
        )

        response = self.client.get(reverse('gamenet:recent_sales_page'), {'per_page': 50})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'جدول آیتم‌های فروخته‌شده')
        self.assertNotContains(response, 'گزارش ماهانه فروش هر جنس')
        self.assertContains(response, 'بیشترین فروش از نظر تعداد')
        self.assertContains(response, 'پرفروش‌ترین دسته‌بندی')
        self.assertContains(response, p1.name)
        self.assertContains(response, p2.name)
        self.assertEqual(response.context['per_page'], 50)
        self.assertEqual(response.context['total_records'], 2)
        self.assertEqual(response.context['top_product_by_qty']['product__name'], p1.name)
        self.assertEqual(response.context['top_product_by_revenue']['product__name'], p1.name)
        self.assertEqual(response.context['top_category_by_qty']['category_name'], 'بدون دسته‌بندی')

    def test_quick_category_create_from_product_page_works_with_minimal_fields(self):
        target = reverse('gamenet:product_list')
        response = self.client.post(reverse('gamenet:category_create'), {
            'source': 'product_list',
            'name': 'نوشیدنی سریع',
            'icon': '',
            'color': '',
            'order': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], target)

        created = ProductCategory.objects.get(gamenet=self.gamenet, name='نوشیدنی سریع')
        self.assertEqual(created.icon, 'fas fa-tag')
        self.assertEqual(created.color, '#7c3aed')
        self.assertEqual(created.order, 0)

    def test_quick_category_create_from_product_page_handles_missing_name(self):
        target = reverse('gamenet:product_list')
        response = self.client.post(reverse('gamenet:category_create'), {
            'source': 'product_list',
            'name': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], target)
        self.assertEqual(ProductCategory.objects.filter(gamenet=self.gamenet).count(), 0)

    def test_tournament_create_supports_private_visibility_and_filtering(self):
        game = Game.objects.create(gamenet=self.gamenet, name='FIFA', genre='Sports')
        start_dt = timezone.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(hours=3)

        response = self.client.post(reverse('gamenet:tournament_create'), {
            'name': 'جام شبانه',
            'game': game.id,
            'description': 'مسابقه تستی',
            'start_date': start_dt.strftime('%Y-%m-%dT%H:%M'),
            'end_date': end_dt.strftime('%Y-%m-%dT%H:%M'),
            'entry_fee': '50000',
            'prize_pool': '500000',
            'max_participants': '16',
            'status': 'upcoming',
            'visibility': 'private',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('gamenet:tournament_list'))

        tournament = Tournament.objects.get(gamenet=self.gamenet, name='جام شبانه')
        self.assertEqual(tournament.visibility, 'private')

        private_list = self.client.get(reverse('gamenet:tournament_list'), {'visibility': 'private'})
        self.assertContains(private_list, 'جام شبانه')

        public_list = self.client.get(reverse('gamenet:tournament_list'), {'visibility': 'public'})
        self.assertNotContains(public_list, 'جام شبانه')

    def test_tournament_edit_updates_visibility(self):
        game = Game.objects.create(gamenet=self.gamenet, name='PES', genre='Sports')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام هفتگی',
            game=game,
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=2, hours=2),
            entry_fee=Decimal('0'),
            prize_pool=Decimal('0'),
            max_participants=8,
            status='upcoming',
            visibility='private',
        )

        response = self.client.post(reverse('gamenet:tournament_edit', args=[tournament.id]), {
            'name': 'جام هفتگی آپدیت',
            'game': game.id,
            'description': 'ویرایش شده',
            'start_date': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            'end_date': (timezone.now() + timedelta(days=3, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'entry_fee': '10000',
            'prize_pool': '250000',
            'max_participants': '12',
            'status': 'upcoming',
            'visibility': 'public',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('gamenet:tournament_detail', args=[tournament.id]))

        tournament.refresh_from_db()
        self.assertEqual(tournament.name, 'جام هفتگی آپدیت')
        self.assertEqual(tournament.visibility, 'public')

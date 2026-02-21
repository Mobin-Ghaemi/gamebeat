import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Subscription
from gamenet.models import Device, Game, GameNet, Order, OrderItem, Product, ProductCategory, Session, Tournament, TournamentMatch, TournamentParticipant


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

    def test_tournament_create_rejects_past_start_date(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Tekken', genre='Fighting')
        start_dt = timezone.now() - timedelta(days=1)
        end_dt = timezone.now() + timedelta(days=1)

        response = self.client.post(reverse('gamenet:tournament_create'), {
            'name': 'جام تاریخ گذشته',
            'game': game.id,
            'description': 'نباید ثبت شود',
            'start_date': start_dt.strftime('%Y-%m-%dT%H:%M'),
            'end_date': end_dt.strftime('%Y-%m-%dT%H:%M'),
            'entry_fee': '10000',
            'prize_pool': '50000',
            'max_participants': '8',
            'status': 'upcoming',
            'visibility': 'public',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'این تاریخ برای گذشته است')
        self.assertFalse(Tournament.objects.filter(gamenet=self.gamenet, name='جام تاریخ گذشته').exists())

    def test_tournament_create_rejects_end_date_before_start_date(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Dota 2', genre='MOBA')
        start_dt = timezone.now() + timedelta(days=4)
        end_dt = timezone.now() + timedelta(days=3)

        response = self.client.post(reverse('gamenet:tournament_create'), {
            'name': 'جام ترتیب تاریخ',
            'game': game.id,
            'description': 'پایان نباید قبل از شروع باشد',
            'start_date': start_dt.strftime('%Y-%m-%dT%H:%M'),
            'end_date': end_dt.strftime('%Y-%m-%dT%H:%M'),
            'entry_fee': '10000',
            'prize_pool': '100000',
            'max_participants': '8',
            'status': 'upcoming',
            'visibility': 'public',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد')
        self.assertFalse(Tournament.objects.filter(gamenet=self.gamenet, name='جام ترتیب تاریخ').exists())

    def test_tournament_create_accepts_persian_digits_in_numeric_fields(self):
        game = Game.objects.create(gamenet=self.gamenet, name='COD', genre='Action')
        start_dt = timezone.now() + timedelta(days=2)
        end_dt = start_dt + timedelta(hours=2)

        response = self.client.post(reverse('gamenet:tournament_create'), {
            'name': 'جام اعداد فارسی',
            'game': game.id,
            'description': 'تست اعداد فارسی',
            'start_date': start_dt.strftime('%Y-%m-%dT%H:%M'),
            'end_date': end_dt.strftime('%Y-%m-%dT%H:%M'),
            'entry_fee': '۵۰,۰۰۰',
            'prize_pool': '۲۵۰٬۰۰۰',
            'max_participants': '۱۶',
            'status': 'upcoming',
            'visibility': 'public',
        })

        self.assertEqual(response.status_code, 302)
        created = Tournament.objects.get(gamenet=self.gamenet, name='جام اعداد فارسی')
        self.assertEqual(created.entry_fee, Decimal('50000'))
        self.assertEqual(created.prize_pool, Decimal('250000'))
        self.assertEqual(created.max_participants, 16)

    def test_tournament_create_accepts_jalali_date_strings(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Fortnite', genre='Battle Royale')

        response = self.client.post(reverse('gamenet:tournament_create'), {
            'name': 'جام شمسی',
            'game': game.id,
            'description': 'تست تاریخ شمسی',
            'start_date': '1404-12-15 20:30:00',
            'end_date': '1404-12-16 23:59:00',
            'entry_fee': '20000',
            'prize_pool': '200000',
            'max_participants': '16',
            'status': 'upcoming',
            'visibility': 'public',
        })

        self.assertEqual(response.status_code, 302)
        created = Tournament.objects.get(gamenet=self.gamenet, name='جام شمسی')
        self.assertGreaterEqual(created.start_date.year, 2025)

    def test_tournament_manage_page_and_status_update(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Valorant', genre='FPS')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام مدیریت',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            entry_fee=Decimal('10000'),
            prize_pool=Decimal('100000'),
            max_participants=8,
            status='upcoming',
            visibility='public',
        )

        page = self.client.get(reverse('gamenet:tournament_manage', args=[tournament.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'مدیریت مسابقه')

        update = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'update_status',
            'status': 'ongoing',
        })
        self.assertEqual(update.status_code, 302)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, 'ongoing')

    def test_tournament_manage_updates_and_deletes_participant(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Apex', genre='Battle Royale')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام شرکت‌کننده',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            entry_fee=Decimal('0'),
            prize_pool=Decimal('0'),
            max_participants=8,
            status='upcoming',
            visibility='public',
        )
        participant = TournamentParticipant.objects.create(
            tournament=tournament,
            name='Player One',
            phone='09120000000',
            gamer_tag='P1',
        )

        update = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'update_participant',
            'participant_id': participant.id,
            'paid': '1',
            'rank': '۲',
        })
        self.assertEqual(update.status_code, 302)
        participant.refresh_from_db()
        self.assertTrue(participant.paid)
        self.assertEqual(participant.rank, 2)

        delete = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'delete_participant',
            'participant_id': participant.id,
        })
        self.assertEqual(delete.status_code, 302)
        self.assertFalse(TournamentParticipant.objects.filter(id=participant.id).exists())

    def test_tournament_manage_manual_add_participant(self):
        game = Game.objects.create(gamenet=self.gamenet, name='CS2', genre='FPS')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام دستی',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            max_participants=8,
            status='upcoming',
            visibility='public',
        )

        response = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'create_participant',
            'name': 'Alpha Team',
            'phone': '',
            'gamer_tag': 'ALPHA',
            'paid': '1',
        })
        self.assertEqual(response.status_code, 302)

        created = TournamentParticipant.objects.get(tournament=tournament, name='Alpha Team')
        self.assertTrue(created.paid)
        self.assertTrue(created.phone)

    def test_tournament_bracket_progression_with_odd_participants(self):
        game = Game.objects.create(gamenet=self.gamenet, name='R6', genre='Tactical')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام براکت',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            max_participants=8,
            status='upcoming',
            visibility='public',
        )
        p1 = TournamentParticipant.objects.create(tournament=tournament, name='P1', phone='09120000001')
        p2 = TournamentParticipant.objects.create(tournament=tournament, name='P2', phone='09120000002')
        p3 = TournamentParticipant.objects.create(tournament=tournament, name='P3', phone='09120000003')

        start_resp = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'start_tournament',
        })
        self.assertEqual(start_resp.status_code, 302)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, 'ongoing')
        self.assertFalse(tournament.registration_open)

        round1 = list(TournamentMatch.objects.filter(tournament=tournament, round_number=1).order_by('match_number'))
        self.assertEqual(len(round1), 2)
        self.assertTrue(any(match.status == 'bye' for match in round1))
        pending_match = next(match for match in round1 if match.status == 'pending')

        winner_id = pending_match.participant1_id or pending_match.participant2_id
        resolve_round1 = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'set_match_winner',
            'match_id': pending_match.id,
            'winner_id': winner_id,
        })
        self.assertEqual(resolve_round1.status_code, 302)
        self.assertTrue(TournamentMatch.objects.filter(tournament=tournament, round_number=2).exists())

        final_match = TournamentMatch.objects.get(tournament=tournament, round_number=2)
        final_winner = final_match.participant1_id or final_match.participant2_id
        resolve_final = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'set_match_winner',
            'match_id': final_match.id,
            'winner_id': final_winner,
        })
        self.assertEqual(resolve_final.status_code, 302)

        tournament.refresh_from_db()
        self.assertEqual(tournament.status, 'completed')
        self.assertIsNotNone(tournament.champion_id)
        self.assertIn(tournament.champion_id, {p1.id, p2.id, p3.id})

    def test_tournament_register_respects_registration_open(self):
        game = Game.objects.create(gamenet=self.gamenet, name='PUBG', genre='BR')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام بسته',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            max_participants=8,
            status='upcoming',
            visibility='public',
            registration_open=False,
        )

        response = self.client.post(reverse('gamenet:tournament_register', args=[tournament.id]), {
            'name': 'Blocked User',
            'phone': '09120000009',
            'gamer_tag': 'BU',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TournamentParticipant.objects.filter(tournament=tournament, phone='09120000009').exists())

    def test_tournament_manage_toggles_public_participant_visibility(self):
        game = Game.objects.create(gamenet=self.gamenet, name='LoL', genre='MOBA')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام نمایش',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            max_participants=8,
            status='upcoming',
            visibility='public',
            show_participants_public=True,
        )

        response = self.client.post(reverse('gamenet:tournament_manage', args=[tournament.id]), {
            'action': 'toggle_public_participants',
            'show_participants_public': '0',
        })
        self.assertEqual(response.status_code, 302)
        tournament.refresh_from_db()
        self.assertFalse(tournament.show_participants_public)

    def test_tournament_detail_prioritizes_results_after_start(self):
        game = Game.objects.create(gamenet=self.gamenet, name='Overwatch', genre='FPS')
        tournament = Tournament.objects.create(
            gamenet=self.gamenet,
            name='جام نتایج',
            game=game,
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1, hours=2),
            max_participants=8,
            status='ongoing',
            visibility='public',
            show_participants_public=True,
        )
        p1 = TournamentParticipant.objects.create(tournament=tournament, name='A', phone='09120000111')
        p2 = TournamentParticipant.objects.create(tournament=tournament, name='B', phone='09120000112')
        TournamentMatch.objects.create(
            tournament=tournament,
            round_number=1,
            match_number=1,
            participant1=p1,
            participant2=p2,
            winner=p1,
            status='completed',
        )

        response = self.client.get(reverse('gamenet:tournament_detail', args=[tournament.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'نتایج مسابقه')
        self.assertNotContains(response, '<table class=\"participants-table\">', html=False)

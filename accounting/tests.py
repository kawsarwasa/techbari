from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from inventory.models import Warehouse
from payments.models import PaymentTransaction
from payments.services import capture_sales_payment
from sales.models import SalesOrder
from sales.services import transition_order

from .models import Account, AccountingEvent, AccountingPeriod, JournalEntry
from .services import (
    AccountingError,
    account_balance,
    close_period,
    post_journal,
    reopen_period,
    reverse_journal,
    trial_balance,
)


class AccountingBase(TestCase):
    def setUp(self):
        self.cash = Account.objects.get(code="1000")
        self.receivable = Account.objects.get(code="1100")
        self.opening_equity = Account.objects.get(code="3000")
        self.sales = Account.objects.get(code="4000")
        self.warehouse = Warehouse.objects.create(
            name="Accounting Warehouse",
            code="ACCT-WH",
            is_default=True,
            is_active=True,
        )

    def manual_journal(self, amount="100.00", source_key=None):
        value = Decimal(amount)
        return post_journal(
            entry_date=date(2026, 9, 7),
            source_type=JournalEntry.SourceType.MANUAL,
            source_key=source_key,
            source_reference="MANUAL-TEST",
            description="Accounting test journal",
            lines=[
                {"account": self.cash, "debit": value, "credit": Decimal("0.00"), "memo": "Cash"},
                {"account": self.opening_equity, "debit": Decimal("0.00"), "credit": value, "memo": "Equity"},
            ],
            actor="Test",
        )


class AccountingModelServiceTests(AccountingBase):
    def test_system_chart_of_accounts_is_seeded(self):
        codes = set(Account.objects.filter(is_system=True).values_list("code", flat=True))
        self.assertTrue({"1000", "1100", "1200", "2000", "3000", "4000", "4090", "5000", "6100"}.issubset(codes))

    def test_balanced_journal_posts_and_trial_balance_balances(self):
        journal = self.manual_journal("125.50")
        self.assertEqual(journal.status, JournalEntry.Status.POSTED)
        self.assertEqual(journal.total_debit, Decimal("125.50"))
        self.assertEqual(journal.total_credit, Decimal("125.50"))
        rows, total_debit, total_credit = trial_balance()
        self.assertTrue(rows)
        self.assertEqual(total_debit, Decimal("125.50"))
        self.assertEqual(total_credit, Decimal("125.50"))

    def test_unbalanced_and_protected_manual_postings_are_blocked(self):
        with self.assertRaises(AccountingError):
            post_journal(
                entry_date=date(2026, 9, 7),
                source_type=JournalEntry.SourceType.MANUAL,
                description="Unbalanced",
                lines=[
                    {"account": self.cash, "debit": Decimal("10.00"), "credit": Decimal("0.00")},
                    {"account": self.opening_equity, "debit": Decimal("0.00"), "credit": Decimal("9.00")},
                ],
            )
        with self.assertRaises(AccountingError):
            post_journal(
                entry_date=date(2026, 9, 7),
                source_type=JournalEntry.SourceType.MANUAL,
                description="Protected account",
                lines=[
                    {"account": self.receivable, "debit": Decimal("10.00"), "credit": Decimal("0.00")},
                    {"account": self.opening_equity, "debit": Decimal("0.00"), "credit": Decimal("10.00")},
                ],
            )
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_source_key_is_idempotent(self):
        first = self.manual_journal("20.00", source_key="test:once")
        second = self.manual_journal("99.00", source_key="test:once")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(JournalEntry.objects.filter(source_key="test:once").count(), 1)
        self.assertEqual(first.total_debit, Decimal("20.00"))

    def test_posted_journal_is_immutable_and_reversal_zeroes_balance(self):
        journal = self.manual_journal("75.00")
        journal.description = "Tampered"
        with self.assertRaises(ValidationError):
            journal.save()
        first_event = journal.events.first()
        first_event.note = "Tampered"
        with self.assertRaises(ValidationError):
            first_event.save()

        reversal = reverse_journal(
            journal=journal,
            reversal_date=date(2026, 9, 8),
            reason="Correction",
            actor="Test",
        )
        journal.refresh_from_db()
        self.assertEqual(journal.status, JournalEntry.Status.REVERSED)
        self.assertEqual(reversal.source_type, JournalEntry.SourceType.REVERSAL)
        self.assertEqual(reversal.reversal_of_id, journal.pk)
        self.assertEqual(account_balance(self.cash), Decimal("0.00"))
        self.assertEqual(account_balance(self.opening_equity), Decimal("0.00"))

    def test_closed_period_blocks_posting_and_reopen_allows_it(self):
        period = AccountingPeriod.objects.create(
            name="September 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        close_period(period=period, actor="Test")
        with self.assertRaises(AccountingError):
            self.manual_journal("10.00")
        reopen_period(period=period, actor="Test")
        journal = self.manual_journal("10.00")
        self.assertEqual(journal.status, JournalEntry.Status.POSTED)

    def test_completed_sale_posts_revenue_automatically(self):
        order = SalesOrder.objects.create(
            order_number="TB-ACCT-SALE",
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.MANUAL,
            status=SalesOrder.Status.CONFIRMED,
            order_date=date(2026, 9, 7),
            shipping_name="Accounting Customer",
            shipping_phone="01700000001",
            subtotal=Decimal("100.00"),
            grand_total=Decimal("100.00"),
        )
        transition_order(order=order, new_status=SalesOrder.Status.COMPLETED, actor="Test")
        journal = JournalEntry.objects.get(source_key=f"sales_order:{order.pk}:revenue")
        self.assertEqual(journal.total_debit, Decimal("100.00"))
        self.assertEqual(account_balance(self.receivable), Decimal("100.00"))
        self.assertEqual(account_balance(self.sales), Decimal("100.00"))

    def test_sale_payment_posts_cash_and_receivable_automatically(self):
        order = SalesOrder.objects.create(
            order_number="TB-ACCT-PAY",
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.MANUAL,
            status=SalesOrder.Status.CONFIRMED,
            order_date=date(2026, 9, 7),
            shipping_name="Payment Customer",
            shipping_phone="01700000002",
            subtotal=Decimal("80.00"),
            grand_total=Decimal("80.00"),
        )
        payment = capture_sales_payment(order=order, amount="50.00", method="cash", actor="Test")
        journal = JournalEntry.objects.get(source_key=f"payment_transaction:{payment.pk}")
        self.assertEqual(payment.kind, PaymentTransaction.Kind.SALE_PAYMENT)
        self.assertEqual(journal.total_debit, Decimal("50.00"))
        self.assertEqual(account_balance(self.cash), Decimal("50.00"))
        self.assertEqual(account_balance(self.receivable), Decimal("-50.00"))


class AccountingDashboardTests(AccountingBase):
    def test_accounting_dashboard_pages_render(self):
        journal = self.manual_journal("30.00")
        routes = [
            reverse("backoffice:accounts"),
            reverse("backoffice:chart_accounts"),
            reverse("backoffice:account_add"),
            reverse("backoffice:journals"),
            reverse("backoffice:journal_add"),
            reverse("backoffice:journal_detail", args=[journal.pk]),
            reverse("backoffice:general_ledger"),
            reverse("backoffice:trial_balance"),
            reverse("backoffice:accounting_periods"),
        ]
        for url in routes:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
        self.assertContains(self.client.get(reverse("backoffice:accounts")), "Accounting & General Ledger")
        self.assertContains(self.client.get(reverse("backoffice:journal_detail", args=[journal.pk])), "Accounting Audit Trail")

    def test_dashboard_posts_balanced_manual_journal(self):
        response = self.client.post(
            reverse("backoffice:journal_add"),
            {
                "entry_date": "2026-09-07",
                "source_reference": "DASH-JE-1",
                "description": "Dashboard balanced entry",
                "account_id": [str(self.cash.pk), str(self.opening_equity.pk)],
                "debit": ["40.00", ""],
                "credit": ["", "40.00"],
                "memo": ["Cash in", "Opening equity"],
            },
        )
        self.assertEqual(response.status_code, 302)
        journal = JournalEntry.objects.get(source_reference="DASH-JE-1")
        self.assertEqual(journal.total_debit, Decimal("40.00"))
        self.assertEqual(journal.total_credit, Decimal("40.00"))

    def test_dashboard_creates_period_and_custom_account(self):
        response = self.client.post(
            reverse("backoffice:account_add"),
            {
                "code": "7000",
                "name": "Test Expense",
                "account_type": Account.Type.EXPENSE,
                "normal_balance": Account.NormalBalance.DEBIT,
                "description": "QA account",
                "allow_manual_entries": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Account.objects.filter(code="7000", is_system=False).exists())

        response = self.client.post(
            reverse("backoffice:accounting_periods"),
            {"name": "October 2026", "start_date": "2026-10-01", "end_date": "2026-10-31"},
        )
        self.assertEqual(response.status_code, 302)
        period = AccountingPeriod.objects.get(name="October 2026")
        self.assertEqual(period.status, AccountingPeriod.Status.OPEN)
        response = self.client.post(reverse("backoffice:accounting_period_toggle", args=[period.pk]))
        self.assertEqual(response.status_code, 302)
        period.refresh_from_db()
        self.assertEqual(period.status, AccountingPeriod.Status.CLOSED)

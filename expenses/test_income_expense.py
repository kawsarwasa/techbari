from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounting.models import Account, JournalEntry
from accounting.services import account_balance
from expenses.models import CashbookEntry, ExpenseCategory
from expenses.services import create_simple_category, register_cashbook_entry, settle_cashbook_entry, void_cashbook_entry


class IncomeExpenseServiceTests(TestCase):
    def setUp(self):
        self.salary = ExpenseCategory.objects.get(code="SALARY")
        self.service = ExpenseCategory.objects.get(code="SERVICE")
        self.cash = Account.objects.get(code="1000")
        self.bank = Account.objects.get(code="1010")

    def test_due_expense_posts_expense_and_other_payable(self):
        entry = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.EXPENSE,
            category=self.salary,
            counterparty="Rahim Ahmed",
            description="September salary",
            amount=Decimal("25000.00"),
            due_date=date(2026, 10, 5),
        )
        entry = register_cashbook_entry(entry=entry, actor="Test")

        self.assertEqual(entry.payment_status, "Due")
        self.assertEqual(entry.due_amount, Decimal("25000.00"))
        journal = JournalEntry.objects.get(source_key=entry.accounting_source_key)
        lines = {row.account.code: (row.debit, row.credit) for row in journal.lines.all()}
        self.assertEqual(lines["6300"], (Decimal("25000.00"), Decimal("0.00")))
        self.assertEqual(lines["2050"], (Decimal("0.00"), Decimal("25000.00")))

    def test_partial_expense_then_full_payment_tracks_due(self):
        entry = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.EXPENSE,
            category=self.salary,
            amount=Decimal("25000.00"),
        )
        entry = register_cashbook_entry(
            entry=entry,
            initial_amount=Decimal("10000.00"),
            payment_account=self.bank,
            actor="Test",
        )
        entry = CashbookEntry.objects.prefetch_related("settlements").get(pk=entry.pk)
        self.assertEqual(entry.payment_status, "Partial")
        self.assertEqual(entry.due_amount, Decimal("15000.00"))

        settlement = entry.settlements.first()
        settlement_journal = JournalEntry.objects.get(source_key=settlement.accounting_source_key)
        lines = {row.account.code: (row.debit, row.credit) for row in settlement_journal.lines.all()}
        self.assertEqual(lines["2050"], (Decimal("10000.00"), Decimal("0.00")))
        self.assertEqual(lines["1010"], (Decimal("0.00"), Decimal("10000.00")))

        settle_cashbook_entry(
            entry=entry,
            amount=Decimal("15000.00"),
            payment_account=self.cash,
            settlement_date=date(2026, 9, 25),
            actor="Test",
        )
        entry = CashbookEntry.objects.prefetch_related("settlements").get(pk=entry.pk)
        self.assertEqual(entry.payment_status, "Paid")
        self.assertEqual(entry.due_amount, Decimal("0.00"))

    def test_due_income_and_partial_receipt_use_other_receivable(self):
        entry = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.INCOME,
            category=self.service,
            counterparty="ABC Shop",
            amount=Decimal("8000.00"),
        )
        entry = register_cashbook_entry(entry=entry, actor="Test")

        recognition = JournalEntry.objects.get(source_key=entry.accounting_source_key)
        lines = {row.account.code: (row.debit, row.credit) for row in recognition.lines.all()}
        self.assertEqual(lines["1150"], (Decimal("8000.00"), Decimal("0.00")))
        self.assertEqual(lines["4020"], (Decimal("0.00"), Decimal("8000.00")))

        settle_cashbook_entry(
            entry=entry,
            amount=Decimal("3000.00"),
            payment_account=self.cash,
            settlement_date=date(2026, 9, 21),
            actor="Test",
        )
        entry = CashbookEntry.objects.prefetch_related("settlements").get(pk=entry.pk)
        self.assertEqual(entry.due_amount, Decimal("5000.00"))
        settlement = entry.settlements.first()
        receipt_journal = JournalEntry.objects.get(source_key=settlement.accounting_source_key)
        lines = {row.account.code: (row.debit, row.credit) for row in receipt_journal.lines.all()}
        self.assertEqual(lines["1000"], (Decimal("3000.00"), Decimal("0.00")))
        self.assertEqual(lines["1150"], (Decimal("0.00"), Decimal("3000.00")))

    def test_simple_category_creates_hidden_matching_gl_account(self):
        category = create_simple_category(
            entry_type=ExpenseCategory.EntryType.INCOME,
            name="Training Income",
            actor="Test",
        )
        self.assertEqual(category.account.account_type, Account.Type.REVENUE)
        self.assertEqual(category.account.normal_balance, Account.NormalBalance.CREDIT)
        self.assertFalse(category.account.allow_manual_entries)
        self.assertTrue(category.code.startswith("INC-"))

    def test_void_reverses_recognition_and_settlements(self):
        entry = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.INCOME,
            category=self.service,
            amount=Decimal("5000.00"),
        )
        entry = register_cashbook_entry(
            entry=entry,
            initial_amount=Decimal("5000.00"),
            payment_account=self.cash,
            actor="Test",
        )
        void_cashbook_entry(
            entry=entry,
            reason="Duplicate entry",
            reversal_date=date(2026, 9, 20),
            actor="Test",
        )
        entry.refresh_from_db()
        self.assertTrue(entry.is_voided)
        self.assertEqual(account_balance(self.service.account), Decimal("0.00"))


class IncomeExpenseDashboardTests(TestCase):
    def test_pages_render(self):
        self.assertEqual(self.client.get(reverse("backoffice:income_expense")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:income_expense_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:income_expense_categories")).status_code, 200)

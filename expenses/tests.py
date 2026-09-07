from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.models import Account, AccountingPeriod, JournalEntry
from accounting.services import account_balance, accounting_summary

from .models import Expense, ExpenseCategory, ExpenseEvent
from .services import (
    ExpenseError,
    approve_expense,
    cancel_expense,
    pay_expense,
    register_expense,
    reject_expense,
    submit_expense,
    void_paid_expense,
)


class ExpenseBase(TestCase):
    def setUp(self):
        self.category = ExpenseCategory.objects.get(code="OFFICE")
        self.cash_account = Account.objects.get(code="1000")
        self.bank_account = Account.objects.get(code="1010")
        self.bkash_account = Account.objects.get(code="1030")

    def make_expense(self, *, amount="150.00", status=Expense.Status.DRAFT, description="Printer paper"):
        expense = Expense(
            expense_date=date(2026, 9, 7),
            category=self.category,
            payee="Office Shop",
            description=description,
            amount=Decimal(amount),
            preferred_payment_method=Expense.Method.CASH,
            receipt_no="RCPT-001",
        )
        register_expense(expense, actor="Test")
        if status == Expense.Status.PENDING:
            submit_expense(expense=expense, actor="Test")
        elif status == Expense.Status.APPROVED:
            submit_expense(expense=expense, actor="Test")
            approve_expense(expense=expense, actor="Approver")
        return Expense.objects.get(pk=expense.pk)


class ExpenseModelServiceTests(ExpenseBase):
    def test_default_categories_and_expense_accounts_are_seeded(self):
        codes = set(ExpenseCategory.objects.values_list("code", flat=True))
        self.assertTrue({"RENT", "UTIL", "MKT", "OFFICE", "COMMS", "TRAVEL", "REPAIR", "BANKFEE", "PRO", "STAFF", "SALARY", "COURIER", "OTHER"}.issubset(codes))
        self.assertEqual(Account.objects.get(code="6230").account_type, Account.Type.EXPENSE)
        self.assertEqual(Account.objects.get(code="6300").account_type, Account.Type.EXPENSE)
        self.assertEqual(ExpenseCategory.objects.get(code="COURIER").account.code, "6100")

    def test_category_must_map_to_expense_account(self):
        category = ExpenseCategory(code="BAD", name="Bad Mapping", account=Account.objects.get(code="1000"))
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_draft_submit_approve_reject_and_cancel_rules(self):
        expense = self.make_expense()
        submit_expense(expense=expense, actor="Requester")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        approve_expense(expense=expense, actor="Approver")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        self.assertEqual(expense.approved_by, "Approver")
        with self.assertRaises(ExpenseError):
            reject_expense(expense=expense, actor="Approver")
        cancel_expense(expense=expense, actor="Approver")
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.CANCELLED)

        second = self.make_expense()
        submit_expense(expense=second, actor="Requester")
        reject_expense(expense=second, note="Not business related", actor="Approver")
        second.refresh_from_db()
        self.assertEqual(second.status, Expense.Status.REJECTED)

    def test_approved_cash_payment_posts_balanced_accounting_journal(self):
        expense = self.make_expense(status=Expense.Status.APPROVED, amount="250.00")
        pay_expense(
            expense=expense,
            payment_method="cash",
            payment_account=self.cash_account,
            payment_date=date(2026, 9, 7),
            actor="Cashier",
        )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PAID)
        self.assertEqual(expense.payment_account, self.cash_account)
        journal = JournalEntry.objects.get(source_key=expense.accounting_source_key)
        self.assertEqual(journal.source_type, JournalEntry.SourceType.EXPENSE)
        self.assertEqual(journal.total_debit, Decimal("250.00"))
        self.assertEqual(journal.total_credit, Decimal("250.00"))
        lines = {line.account.code: (line.debit, line.credit) for line in journal.lines.all()}
        self.assertEqual(lines["6230"], (Decimal("250.00"), Decimal("0.00")))
        self.assertEqual(lines["1000"], (Decimal("0.00"), Decimal("250.00")))
        self.assertEqual(accounting_summary()["expenses"], Decimal("250.00"))

    def test_non_cash_payment_requires_reference_and_uses_selected_asset_account(self):
        expense = self.make_expense(status=Expense.Status.APPROVED)
        with self.assertRaises(ExpenseError):
            pay_expense(
                expense=expense,
                payment_method="bkash",
                payment_account=self.bkash_account,
                payment_date=date(2026, 9, 7),
                actor="Cashier",
            )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        pay_expense(
            expense=expense,
            payment_method="bkash",
            payment_account=self.bkash_account,
            payment_reference="BK-EXP-1",
            payment_date=date(2026, 9, 7),
            actor="Cashier",
        )
        journal = JournalEntry.objects.get(source_key=expense.accounting_source_key)
        bkash_line = journal.lines.get(account__code="1030")
        self.assertEqual(bkash_line.credit, Decimal("150.00"))

    def test_payment_account_must_be_active_manual_asset(self):
        expense = self.make_expense(status=Expense.Status.APPROVED)
        with self.assertRaises(ExpenseError):
            pay_expense(
                expense=expense,
                payment_method="cash",
                payment_account=Account.objects.get(code="1200"),
                payment_date=date(2026, 9, 7),
                actor="Cashier",
            )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)

    def test_payment_is_blocked_in_closed_accounting_period_atomically(self):
        expense = self.make_expense(status=Expense.Status.APPROVED)
        AccountingPeriod.objects.create(
            name="September 2026 Closed",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            status=AccountingPeriod.Status.CLOSED,
            closed_at=timezone.now(),
            closed_by="Finance",
        )
        with self.assertRaises(ExpenseError):
            pay_expense(
                expense=expense,
                payment_method="cash",
                payment_account=self.cash_account,
                payment_date=date(2026, 9, 7),
                actor="Cashier",
            )
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        self.assertFalse(JournalEntry.objects.filter(source_key=expense.accounting_source_key).exists())

    def test_paid_expense_void_creates_reversal_without_deleting_history(self):
        expense = self.make_expense(status=Expense.Status.APPROVED, amount="90.00")
        pay_expense(
            expense=expense,
            payment_method="cash",
            payment_account=self.cash_account,
            payment_date=date(2026, 9, 7),
            actor="Cashier",
        )
        journal = JournalEntry.objects.get(source_key=expense.accounting_source_key)
        void_paid_expense(expense=expense, reason="Duplicate receipt", reversal_date=date(2026, 9, 7), actor="Finance")
        expense.refresh_from_db()
        journal.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.VOIDED)
        self.assertEqual(journal.status, JournalEntry.Status.REVERSED)
        self.assertTrue(hasattr(journal, "reversal_entry"))
        self.assertEqual(account_balance(self.category.account), Decimal("0.00"))

    def test_expense_events_are_immutable(self):
        expense = self.make_expense()
        event = expense.events.first()
        event.note = "tamper"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()


class ExpenseDashboardTests(ExpenseBase):
    def test_expense_pages_render_database_data(self):
        expense = self.make_expense(description="Dashboard stationery")
        response = self.client.get(reverse("backoffice:expenses"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, expense.expense_no)
        self.assertContains(response, "Dashboard stationery")
        self.assertEqual(self.client.get(reverse("backoffice:expense_detail", args=[expense.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:expense_categories")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:expense_add")).status_code, 200)

    def test_dashboard_create_submit_approve_and_pay(self):
        attachment = SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 test receipt", content_type="application/pdf")
        response = self.client.post(reverse("backoffice:expense_add"), {
            "expense_date": "2026-09-07",
            "category": self.category.pk,
            "payee": "Dashboard Vendor",
            "description": "Dashboard Expense",
            "amount": "120.00",
            "preferred_payment_method": "bank",
            "receipt_no": "INV-DASH-1",
            "notes": "Created from dashboard",
            "action": "submit",
            "attachment": attachment,
        })
        self.assertEqual(response.status_code, 302)
        expense = Expense.objects.get(description="Dashboard Expense")
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertTrue(bool(expense.attachment))
        self.assertEqual(self.client.post(reverse("backoffice:expense_approve", args=[expense.pk]), {"note": "Approved"}).status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        response = self.client.post(reverse("backoffice:expense_pay", args=[expense.pk]), {
            "payment_method": "bank",
            "payment_account": self.bank_account.pk,
            "payment_reference": "BANK-EXP-1",
            "payment_date": "2026-09-07",
            "note": "Paid",
        })
        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PAID)
        self.assertEqual(expense.payment_account, self.bank_account)
        self.assertTrue(JournalEntry.objects.filter(source_key=expense.accounting_source_key).exists())

    def test_dashboard_rejects_unsupported_attachment(self):
        attachment = SimpleUploadedFile("receipt.exe", b"not allowed", content_type="application/octet-stream")
        response = self.client.post(reverse("backoffice:expense_add"), {
            "expense_date": "2026-09-07",
            "category": self.category.pk,
            "description": "Bad Attachment",
            "amount": "50.00",
            "attachment": attachment,
            "action": "draft",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attachment must be PDF, JPG, JPEG, PNG or WebP.")
        self.assertFalse(Expense.objects.filter(description="Bad Attachment").exists())

    def test_dashboard_can_create_custom_category_and_filter_expenses(self):
        account = Account.objects.get(code="6280")
        response = self.client.post(reverse("backoffice:expense_categories"), {
            "code": "CONSULT",
            "name": "Consulting Special",
            "account": account.pk,
            "description": "Special consulting",
            "sort_order": "95",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        category = ExpenseCategory.objects.get(code="CONSULT")
        expense = Expense(
            expense_date=date(2026, 9, 7),
            category=category,
            payee="Advisor",
            description="Consulting session",
            amount=Decimal("500.00"),
        )
        register_expense(expense, actor="Test")
        response = self.client.get(reverse("backoffice:expenses"), {"category": category.pk, "q": "Advisor"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Consulting session")

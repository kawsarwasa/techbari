from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import Account
from expenses.models import CashbookEntry, ExpenseCategory
from expenses.services import register_cashbook_entry
from reports.after_sales import build_after_sales_report
from reports.financial import build_financial_report


class IncomeExpenseReportTests(TestCase):
    def setUp(self):
        self.cash = Account.objects.get(code="1000")
        self.service = ExpenseCategory.objects.get(code="SERVICE")
        self.salary = ExpenseCategory.objects.get(code="SALARY")

    def test_income_expense_report_and_financial_reports_include_simple_entries(self):
        income = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.INCOME,
            category=self.service,
            counterparty="ABC Shop",
            amount=Decimal("5000.00"),
        )
        register_cashbook_entry(
            entry=income,
            initial_amount=Decimal("5000.00"),
            payment_account=self.cash,
            actor="Test",
        )
        expense = CashbookEntry(
            entry_date=date(2026, 9, 20),
            entry_type=CashbookEntry.EntryType.EXPENSE,
            category=self.salary,
            counterparty="Rahim",
            amount=Decimal("2000.00"),
        )
        register_cashbook_entry(entry=expense, actor="Test")

        report = build_after_sales_report({
            "report": "income_expense",
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
        })
        self.assertEqual(report["report_key"], "income_expense")
        self.assertEqual(len(report["rows"]), 2)
        kpis = {row["label"]: row["value"] for row in report["kpis"]}
        self.assertEqual(kpis["Income"], Decimal("5000.00"))
        self.assertEqual(kpis["Expense"], Decimal("2000.00"))
        self.assertEqual(kpis["Expense Due"], Decimal("2000.00"))

        pnl = build_financial_report({
            "report": "pnl",
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
        })
        pnl_labels = [row["csv"][2] for row in pnl["rows"]]
        self.assertIn("Service Income", pnl_labels)
        self.assertIn("Salaries & Wages", pnl_labels)

        cash_flow = build_financial_report({
            "report": "cash_flow",
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
        })
        self.assertTrue(any(row["csv"][2] == "Operating" for row in cash_flow["rows"]))

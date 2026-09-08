from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.models import Account, JournalEntry
from accounting.services import post_journal
from reports.financial import build_financial_report


ZERO = Decimal("0.00")


class FinancialStatementReportTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.start = self.today.replace(day=1)
        self.opening_date = self.start - timedelta(days=1)
        self.cash = Account.objects.get(code="1000")
        self.ar = Account.objects.get(code="1100")
        self.inventory = Account.objects.get(code="1200")
        self.opening_equity = Account.objects.get(code="3000")
        self.sales = Account.objects.get(code="4000")
        self.cogs = Account.objects.get(code="5000")
        self.other_expense = Account.objects.get(code="6990")
        self.equipment = Account.objects.create(
            code="1500",
            name="Equipment",
            account_type=Account.Type.ASSET,
            normal_balance=Account.NormalBalance.DEBIT,
            allow_manual_entries=True,
            is_active=True,
        )
        self.loan = Account.objects.create(
            code="2100",
            name="Business Loan",
            account_type=Account.Type.LIABILITY,
            normal_balance=Account.NormalBalance.CREDIT,
            allow_manual_entries=True,
            is_active=True,
        )
        self._seed_ledger()

    def _post(self, entry_date, source_type, key, description, lines):
        return post_journal(
            entry_date=entry_date,
            source_type=source_type,
            source_key=key,
            source_reference=key,
            description=description,
            lines=lines,
            actor="Reports test",
        )

    def _seed_ledger(self):
        self._post(
            self.opening_date,
            JournalEntry.SourceType.OPENING_BALANCE,
            "financial-test-opening",
            "Opening cash capital",
            [
                {"account": self.cash, "debit": Decimal("1000.00"), "credit": ZERO},
                {"account": self.opening_equity, "debit": ZERO, "credit": Decimal("1000.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.SALE,
            "financial-test-sale",
            "Completed sale",
            [
                {"account": self.ar, "debit": Decimal("500.00"), "credit": ZERO},
                {"account": self.sales, "debit": ZERO, "credit": Decimal("500.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.SALE,
            "financial-test-cogs",
            "Sale COGS",
            [
                {"account": self.cogs, "debit": Decimal("300.00"), "credit": ZERO},
                {"account": self.inventory, "debit": ZERO, "credit": Decimal("300.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.SALE_PAYMENT,
            "financial-test-payment",
            "Customer payment",
            [
                {"account": self.cash, "debit": Decimal("500.00"), "credit": ZERO},
                {"account": self.ar, "debit": ZERO, "credit": Decimal("500.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.EXPENSE,
            "financial-test-expense",
            "Operating expense",
            [
                {"account": self.other_expense, "debit": Decimal("50.00"), "credit": ZERO},
                {"account": self.cash, "debit": ZERO, "credit": Decimal("50.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.MANUAL,
            "financial-test-equipment",
            "Buy equipment",
            [
                {"account": self.equipment, "debit": Decimal("100.00"), "credit": ZERO},
                {"account": self.cash, "debit": ZERO, "credit": Decimal("100.00")},
            ],
        )
        self._post(
            self.start,
            JournalEntry.SourceType.MANUAL,
            "financial-test-loan",
            "Receive business loan",
            [
                {"account": self.cash, "debit": Decimal("200.00"), "credit": ZERO},
                {"account": self.loan, "debit": ZERO, "credit": Decimal("200.00")},
            ],
        )

    def _params(self, report):
        return {
            "report": report,
            "date_from": self.start.isoformat(),
            "date_to": self.today.isoformat(),
        }

    def test_profit_and_loss_uses_general_ledger_activity(self):
        report = build_financial_report(self._params("pnl"))
        kpis = {row["label"]: row["value"] for row in report["kpis"]}
        self.assertEqual(kpis["Net Revenue"], Decimal("500.00"))
        self.assertEqual(kpis["COGS"], Decimal("300.00"))
        self.assertEqual(kpis["Gross Profit"], Decimal("200.00"))
        self.assertEqual(kpis["Operating Expense"], Decimal("50.00"))
        self.assertEqual(kpis["Net Profit"], Decimal("150.00"))

    def test_balance_sheet_balances_with_gl_derived_cumulative_earnings(self):
        report = build_financial_report(self._params("balance_sheet"))
        kpis = {row["label"]: row["value"] for row in report["kpis"]}
        self.assertEqual(kpis["Total Assets"], Decimal("1350.00"))
        self.assertEqual(kpis["Total Liabilities"], Decimal("200.00"))
        self.assertEqual(kpis["Total Equity"], Decimal("1150.00"))
        self.assertEqual(kpis["Cumulative Earnings"], Decimal("150.00"))
        self.assertEqual(kpis["Equation Difference"], Decimal("0.00"))

    def test_cash_flow_reconciles_opening_and_closing_cash(self):
        report = build_financial_report(self._params("cash_flow"))
        kpis = {row["label"]: row["value"] for row in report["kpis"]}
        self.assertEqual(kpis["Opening Cash"], Decimal("1000.00"))
        self.assertEqual(kpis["Operating Cash Flow"], Decimal("450.00"))
        self.assertEqual(kpis["Investing Cash Flow"], Decimal("-100.00"))
        self.assertEqual(kpis["Financing Cash Flow"], Decimal("200.00"))
        self.assertEqual(kpis["Closing Cash"], Decimal("1550.00"))
        self.assertEqual(kpis["Reconciliation Difference"], Decimal("0.00"))

    def test_trial_balance_is_balanced_as_of_date(self):
        report = build_financial_report(self._params("trial_balance"))
        kpis = {row["label"]: row["value"] for row in report["kpis"]}
        self.assertEqual(kpis["Total Debit"], kpis["Total Credit"])
        self.assertEqual(kpis["Difference"], Decimal("0.00"))

    def test_financial_tabs_render_and_export_csv(self):
        url = reverse("backoffice:reports")
        for report_key in ("pnl", "balance_sheet", "cash_flow", "trial_balance"):
            response = self.client.get(url, self._params(report_key))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "P&amp;L")
            self.assertContains(response, "Balance Sheet")
            self.assertContains(response, "Cash Flow")
            self.assertContains(response, "Trial Balance")
            csv_response = self.client.get(url, {**self._params(report_key), "export": "csv"})
            self.assertEqual(csv_response.status_code, 200)
            self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")

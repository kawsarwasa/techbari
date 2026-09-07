from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Account, AccountingEvent, AccountingPeriod, JournalEntry, JournalLine, ZERO


MONEY = Decimal("0.01")

SYSTEM_ACCOUNTS = {
    "cash": "1000",
    "bank": "1010",
    "card": "1020",
    "bkash": "1030",
    "nagad": "1040",
    "other": "1090",
    "receivable": "1100",
    "inventory": "1200",
    "payable": "2000",
    "opening_equity": "3000",
    "sales": "4000",
    "shipping_revenue": "4010",
    "sales_returns": "4090",
    "cogs": "5000",
    "courier_fees": "6100",
    "other_expense": "6990",
}

PAYMENT_ASSET_CODES = {
    "cash": SYSTEM_ACCOUNTS["cash"],
    "bank": SYSTEM_ACCOUNTS["bank"],
    "card": SYSTEM_ACCOUNTS["card"],
    "bkash": SYSTEM_ACCOUNTS["bkash"],
    "nagad": SYSTEM_ACCOUNTS["nagad"],
    "other": SYSTEM_ACCOUNTS["other"],
}


class AccountingError(ValidationError):
    pass


def _decimal(value, label="amount"):
    try:
        return Decimal(str(value if value not in (None, "") else "0")).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AccountingError(f"Invalid {label}.") from exc


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _account(code):
    try:
        return Account.objects.get(code=code, is_active=True)
    except Account.DoesNotExist as exc:
        raise AccountingError(f"Accounting system account {code} is missing or inactive. Run migrations and review Chart of Accounts.") from exc


def payment_asset_code(method):
    return PAYMENT_ASSET_CODES.get(str(method or "").strip().lower(), SYSTEM_ACCOUNTS["other"])


def ensure_open_period(entry_date):
    if AccountingPeriod.objects.filter(
        status=AccountingPeriod.Status.CLOSED,
        start_date__lte=entry_date,
        end_date__gte=entry_date,
    ).exists():
        raise AccountingError(f"Accounting period containing {entry_date} is closed.")


def _event(journal, event, *, note="", actor=""):
    return AccountingEvent.objects.create(journal=journal, event=event, note=note or "", actor=actor or "")


@transaction.atomic
def post_journal(
    *,
    entry_date,
    source_type,
    source_key=None,
    source_reference="",
    description,
    lines,
    actor="",
    reversal_of=None,
):
    entry_date = entry_date or timezone.localdate()
    ensure_open_period(entry_date)
    if source_key:
        existing = JournalEntry.objects.filter(source_key=source_key).first()
        if existing:
            return existing
    if source_type not in {value for value, _ in JournalEntry.SourceType.choices}:
        raise AccountingError("Select a valid journal source type.")
    if not lines or len(lines) < 2:
        raise AccountingError("A journal entry requires at least two lines.")

    normalized = []
    debit_total = ZERO
    credit_total = ZERO
    for index, raw in enumerate(lines, start=1):
        raw_account = raw.get("account") or raw.get("account_code")
        account = raw_account if isinstance(raw_account, Account) else _account(str(raw_account or "").strip().upper())
        if not account.is_active:
            raise AccountingError(f"Journal line {index}: account {account.code} is inactive.")
        if source_type == JournalEntry.SourceType.MANUAL and not account.allow_manual_entries:
            raise AccountingError(f"Journal line {index}: account {account.code} does not allow manual postings.")
        debit = _decimal(raw.get("debit"), "debit")
        credit = _decimal(raw.get("credit"), "credit")
        if debit < ZERO or credit < ZERO:
            raise AccountingError("Journal amounts cannot be negative.")
        if (debit > ZERO) == (credit > ZERO):
            raise AccountingError(f"Journal line {index} must contain either a debit or a credit.")
        debit_total += debit
        credit_total += credit
        normalized.append((account, debit, credit, str(raw.get("memo") or "").strip()))

    debit_total = debit_total.quantize(MONEY)
    credit_total = credit_total.quantize(MONEY)
    if debit_total <= ZERO or debit_total != credit_total:
        raise AccountingError(f"Journal is not balanced. Debit {debit_total} / Credit {credit_total}.")

    journal = JournalEntry(
        entry_date=entry_date,
        source_type=source_type,
        source_key=source_key or None,
        source_reference=str(source_reference or "").strip(),
        description=str(description or "").strip() or "Accounting journal",
        status=JournalEntry.Status.DRAFT,
        reversal_of=reversal_of,
        created_by=actor or "",
    )
    journal.full_clean()
    journal.save()
    _event(journal, AccountingEvent.Event.CREATED, note=journal.description, actor=actor)

    for account, debit, credit, memo in normalized:
        line = JournalLine(entry=journal, account=account, debit=debit, credit=credit, memo=memo)
        line.full_clean()
        line.save()

    journal.status = JournalEntry.Status.POSTED
    journal.posted_at = timezone.now()
    journal.full_clean()
    journal.save(update_fields=["status", "posted_at", "updated_at"])
    _event(journal, AccountingEvent.Event.POSTED, note=f"Posted balanced journal {debit_total}.", actor=actor)
    return journal


@transaction.atomic
def reverse_journal(*, journal, reversal_date=None, reason="", actor=""):
    journal = JournalEntry.objects.select_for_update().prefetch_related("lines__account").get(pk=journal.pk)
    if journal.status != JournalEntry.Status.POSTED:
        raise AccountingError("Only a posted journal can be reversed.")
    if hasattr(journal, "reversal_entry"):
        return journal.reversal_entry
    reversal_date = reversal_date or timezone.localdate()
    lines = [
        {
            "account": line.account,
            "debit": line.credit,
            "credit": line.debit,
            "memo": f"Reversal of {journal.entry_no}. {reason}".strip(),
        }
        for line in journal.lines.all()
    ]
    reversal = post_journal(
        entry_date=reversal_date,
        source_type=JournalEntry.SourceType.REVERSAL,
        source_key=f"journal_reversal:{journal.pk}",
        source_reference=journal.entry_no,
        description=f"Reversal of {journal.entry_no}. {reason}".strip(),
        lines=lines,
        actor=actor,
        reversal_of=journal,
    )
    JournalEntry.objects.filter(pk=journal.pk, status=JournalEntry.Status.POSTED).update(
        status=JournalEntry.Status.REVERSED,
        updated_at=timezone.now(),
    )
    journal.status = JournalEntry.Status.REVERSED
    _event(journal, AccountingEvent.Event.REVERSED, note=f"Reversed by {reversal.entry_no}. {reason}".strip(), actor=actor)
    return reversal


@transaction.atomic
def close_period(*, period, actor=""):
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status == AccountingPeriod.Status.CLOSED:
        return period
    unposted = JournalEntry.objects.filter(
        status=JournalEntry.Status.DRAFT,
        entry_date__range=(period.start_date, period.end_date),
    ).exists()
    if unposted:
        raise AccountingError("This period contains Draft journals. Post or remove them before closing.")
    period.status = AccountingPeriod.Status.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = actor or "Dashboard"
    period.full_clean()
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    AccountingEvent.objects.create(event=AccountingEvent.Event.PERIOD, note=f"Closed period {period.name}.", actor=actor or "Dashboard")
    return period


@transaction.atomic
def reopen_period(*, period, actor=""):
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status == AccountingPeriod.Status.OPEN:
        return period
    AccountingPeriod.objects.filter(pk=period.pk).update(
        status=AccountingPeriod.Status.OPEN,
        closed_at=None,
        closed_by="",
        updated_at=timezone.now(),
    )
    period.status = AccountingPeriod.Status.OPEN
    period.closed_at = None
    period.closed_by = ""
    AccountingEvent.objects.create(event=AccountingEvent.Event.PERIOD, note=f"Reopened period {period.name}.", actor=actor or "Dashboard")
    return period


def _net_purchase_unit_cost(purchase_item):
    ordered = Decimal(purchase_item.ordered_quantity or 0)
    if ordered <= ZERO:
        return ZERO
    gross = ordered * (purchase_item.unit_cost or ZERO)
    net = max(gross - (purchase_item.discount_amount or ZERO), ZERO)
    return (net / ordered).quantize(MONEY, rounding=ROUND_HALF_UP)


def variant_weighted_cost(variant_id, *, as_of=None):
    from purchasing.models import PurchaseReceiptItem, PurchaseReturnItem

    receipt_qs = PurchaseReceiptItem.objects.select_related("receipt", "purchase_item").filter(
        purchase_item__variant_id=variant_id
    )
    if as_of:
        receipt_qs = receipt_qs.filter(receipt__received_date__lte=as_of)
    qty = Decimal("0")
    value = ZERO
    for row in receipt_qs:
        unit_cost = _net_purchase_unit_cost(row.purchase_item)
        qty += Decimal(row.quantity)
        value += unit_cost * Decimal(row.quantity)

    return_qs = PurchaseReturnItem.objects.select_related("purchase_return", "purchase_item").filter(
        purchase_item__variant_id=variant_id
    )
    if as_of:
        return_qs = return_qs.filter(purchase_return__return_date__lte=as_of)
    for row in return_qs:
        row_qty = Decimal(row.quantity)
        qty -= row_qty
        value -= (row.unit_cost or ZERO) * row_qty

    if qty <= ZERO or value <= ZERO:
        return ZERO
    return (value / qty).quantize(MONEY, rounding=ROUND_HALF_UP)


def sales_order_cogs(order):
    total = ZERO
    for item in order.items.all():
        quantity = Decimal(item.issued_quantity or 0)
        if quantity <= ZERO:
            continue
        total += variant_weighted_cost(item.variant_id, as_of=order.order_date) * quantity
    return total.quantize(MONEY)


@transaction.atomic
def post_sales_order(order, *, actor="Accounting"):
    from sales.models import SalesOrder

    order = SalesOrder.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
    if order.status != SalesOrder.Status.COMPLETED:
        return None
    product_revenue = max((order.subtotal or ZERO) - (order.discount_amount or ZERO), ZERO)
    shipping_revenue = order.shipping_charge or ZERO
    total = order.grand_total or ZERO
    if total > ZERO:
        lines = [{"account": SYSTEM_ACCOUNTS["receivable"], "debit": total, "credit": ZERO, "memo": order.order_number}]
        if product_revenue > ZERO:
            lines.append({"account": SYSTEM_ACCOUNTS["sales"], "debit": ZERO, "credit": product_revenue, "memo": "Product sales"})
        if shipping_revenue > ZERO:
            lines.append({"account": SYSTEM_ACCOUNTS["shipping_revenue"], "debit": ZERO, "credit": shipping_revenue, "memo": "Customer shipping charge"})
        post_journal(
            entry_date=order.order_date,
            source_type=JournalEntry.SourceType.SALE,
            source_key=f"sales_order:{order.pk}:revenue",
            source_reference=order.order_number,
            description=f"Sale {order.order_number}",
            lines=lines,
            actor=actor,
        )
    cogs = sales_order_cogs(order)
    if cogs > ZERO:
        post_journal(
            entry_date=order.order_date,
            source_type=JournalEntry.SourceType.SALE,
            source_key=f"sales_order:{order.pk}:cogs",
            source_reference=order.order_number,
            description=f"Cost of goods sold for {order.order_number}",
            lines=[
                {"account": SYSTEM_ACCOUNTS["cogs"], "debit": cogs, "credit": ZERO, "memo": "COGS"},
                {"account": SYSTEM_ACCOUNTS["inventory"], "debit": ZERO, "credit": cogs, "memo": "Inventory issued"},
            ],
            actor=actor,
        )
    return order


@transaction.atomic
def post_payment_transaction(payment, *, actor="Accounting"):
    from payments.models import PaymentTransaction

    payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)
    if payment.status not in {PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED}:
        return None
    asset_code = payment_asset_code(payment.method)
    if payment.kind == PaymentTransaction.Kind.SALE_PAYMENT:
        lines = [
            {"account": asset_code, "debit": payment.amount, "credit": ZERO, "memo": payment.transaction_no},
            {"account": SYSTEM_ACCOUNTS["receivable"], "debit": ZERO, "credit": payment.amount, "memo": payment.source_reference},
        ]
        source_type = JournalEntry.SourceType.SALE_PAYMENT
    elif payment.kind in {PaymentTransaction.Kind.REFUND, PaymentTransaction.Kind.REVERSAL}:
        lines = [
            {"account": SYSTEM_ACCOUNTS["receivable"], "debit": payment.amount, "credit": ZERO, "memo": payment.source_reference},
            {"account": asset_code, "debit": ZERO, "credit": payment.amount, "memo": payment.transaction_no},
        ]
        source_type = JournalEntry.SourceType.SALE_PAYMENT
    elif payment.kind == PaymentTransaction.Kind.SUPPLIER_PAYMENT:
        lines = [
            {"account": SYSTEM_ACCOUNTS["payable"], "debit": payment.amount, "credit": ZERO, "memo": payment.source_reference},
            {"account": asset_code, "debit": ZERO, "credit": payment.amount, "memo": payment.transaction_no},
        ]
        source_type = JournalEntry.SourceType.SUPPLIER_PAYMENT
    else:
        return None
    return post_journal(
        entry_date=payment.transaction_date,
        source_type=source_type,
        source_key=f"payment_transaction:{payment.pk}",
        source_reference=payment.source_reference or payment.transaction_no,
        description=f"{payment.get_kind_display()} {payment.transaction_no}",
        lines=lines,
        actor=actor,
    )


@transaction.atomic
def post_purchase_receipt_item(receipt_item, *, actor="Accounting"):
    from purchasing.models import PurchaseReceiptItem

    receipt_item = PurchaseReceiptItem.objects.select_for_update().select_related(
        "receipt", "receipt__purchase", "purchase_item"
    ).get(pk=receipt_item.pk)
    amount = (_net_purchase_unit_cost(receipt_item.purchase_item) * Decimal(receipt_item.quantity)).quantize(MONEY)
    if amount <= ZERO:
        return None
    return post_journal(
        entry_date=receipt_item.receipt.received_date,
        source_type=JournalEntry.SourceType.PURCHASE_RECEIPT,
        source_key=f"purchase_receipt_item:{receipt_item.pk}",
        source_reference=receipt_item.receipt.receipt_no,
        description=f"Goods received for {receipt_item.receipt.purchase.po_number}",
        lines=[
            {"account": SYSTEM_ACCOUNTS["inventory"], "debit": amount, "credit": ZERO, "memo": receipt_item.purchase_item.variant.sku},
            {"account": SYSTEM_ACCOUNTS["payable"], "debit": ZERO, "credit": amount, "memo": receipt_item.receipt.purchase.supplier.name},
        ],
        actor=actor,
    )


@transaction.atomic
def post_purchase_overhead(purchase, *, actor="Accounting"):
    from purchasing.models import PurchaseOrder

    purchase = PurchaseOrder.objects.select_for_update().get(pk=purchase.pk)
    if purchase.status != PurchaseOrder.Status.RECEIVED:
        return None
    delta = ((purchase.shipping_cost or ZERO) + (purchase.other_cost or ZERO) - (purchase.discount_amount or ZERO)).quantize(MONEY)
    if delta == ZERO:
        return None
    if delta > ZERO:
        lines = [
            {"account": SYSTEM_ACCOUNTS["inventory"], "debit": delta, "credit": ZERO, "memo": "Purchase overhead"},
            {"account": SYSTEM_ACCOUNTS["payable"], "debit": ZERO, "credit": delta, "memo": purchase.supplier.name},
        ]
    else:
        amount = abs(delta)
        lines = [
            {"account": SYSTEM_ACCOUNTS["payable"], "debit": amount, "credit": ZERO, "memo": "Purchase discount"},
            {"account": SYSTEM_ACCOUNTS["inventory"], "debit": ZERO, "credit": amount, "memo": purchase.po_number},
        ]
    return post_journal(
        entry_date=purchase.purchase_date,
        source_type=JournalEntry.SourceType.PURCHASE_OVERHEAD,
        source_key=f"purchase_overhead:{purchase.pk}",
        source_reference=purchase.po_number,
        description=f"Purchase shipping/other/discount adjustment for {purchase.po_number}",
        lines=lines,
        actor=actor,
    )


@transaction.atomic
def post_purchase_return_item(return_item, *, actor="Accounting"):
    from purchasing.models import PurchaseReturnItem

    return_item = PurchaseReturnItem.objects.select_for_update().select_related(
        "purchase_return", "purchase_return__purchase", "purchase_item"
    ).get(pk=return_item.pk)
    amount = (Decimal(return_item.quantity) * (return_item.unit_cost or ZERO)).quantize(MONEY)
    if amount <= ZERO:
        return None
    return post_journal(
        entry_date=return_item.purchase_return.return_date,
        source_type=JournalEntry.SourceType.PURCHASE_RETURN,
        source_key=f"purchase_return_item:{return_item.pk}",
        source_reference=return_item.purchase_return.return_no,
        description=f"Supplier return {return_item.purchase_return.return_no}",
        lines=[
            {"account": SYSTEM_ACCOUNTS["payable"], "debit": amount, "credit": ZERO, "memo": return_item.purchase_return.purchase.supplier.name},
            {"account": SYSTEM_ACCOUNTS["inventory"], "debit": ZERO, "credit": amount, "memo": return_item.purchase_item.variant.sku},
        ],
        actor=actor,
    )


@transaction.atomic
def post_sales_return(sales_return, *, actor="Accounting"):
    from returns.models import SalesReturn

    sales_return = SalesReturn.objects.select_for_update().select_related("order").prefetch_related("items").get(pk=sales_return.pk)
    if sales_return.status != SalesReturn.Status.COMPLETED:
        return None
    credit = sales_return.credit_total.quantize(MONEY)
    if credit > ZERO:
        post_journal(
            entry_date=sales_return.completed_date or timezone.localdate(),
            source_type=JournalEntry.SourceType.SALE_RETURN,
            source_key=f"sales_return:{sales_return.pk}:credit",
            source_reference=sales_return.return_no,
            description=f"Sales return credit {sales_return.return_no}",
            lines=[
                {"account": SYSTEM_ACCOUNTS["sales_returns"], "debit": credit, "credit": ZERO, "memo": sales_return.order.order_number},
                {"account": SYSTEM_ACCOUNTS["receivable"], "debit": ZERO, "credit": credit, "memo": sales_return.customer_name},
            ],
            actor=actor,
        )
    restock_cost = ZERO
    for item in sales_return.items.all():
        qty = Decimal(item.restocked_quantity or 0)
        if qty <= ZERO:
            continue
        restock_cost += variant_weighted_cost(item.variant_id, as_of=sales_return.order.order_date) * qty
    restock_cost = restock_cost.quantize(MONEY)
    if restock_cost > ZERO:
        post_journal(
            entry_date=sales_return.completed_date or timezone.localdate(),
            source_type=JournalEntry.SourceType.SALE_RETURN,
            source_key=f"sales_return:{sales_return.pk}:cogs",
            source_reference=sales_return.return_no,
            description=f"Restore returned inventory cost for {sales_return.return_no}",
            lines=[
                {"account": SYSTEM_ACCOUNTS["inventory"], "debit": restock_cost, "credit": ZERO, "memo": "Restocked return"},
                {"account": SYSTEM_ACCOUNTS["cogs"], "debit": ZERO, "credit": restock_cost, "memo": sales_return.order.order_number},
            ],
            actor=actor,
        )
    return sales_return


@transaction.atomic
def post_cod_settlement(settlement, *, actor="Accounting"):
    from shipping.models import CODSettlement

    settlement = CODSettlement.objects.select_for_update().get(pk=settlement.pk)
    deduction = (settlement.courier_deduction or ZERO).quantize(MONEY)
    if deduction <= ZERO:
        return None
    asset_code = payment_asset_code(settlement.payment_method)
    return post_journal(
        entry_date=settlement.settlement_date,
        source_type=JournalEntry.SourceType.COURIER_FEE,
        source_key=f"cod_settlement:{settlement.pk}:deduction",
        source_reference=settlement.settlement_no,
        description=f"Courier deduction / collection fee {settlement.settlement_no}",
        lines=[
            {"account": SYSTEM_ACCOUNTS["courier_fees"], "debit": deduction, "credit": ZERO, "memo": settlement.courier.name},
            {"account": asset_code, "debit": ZERO, "credit": deduction, "memo": settlement.reference},
        ],
        actor=actor,
    )


def post_opening_balances(*, actor="Accounting backfill"):
    from customers.models import Customer
    from purchasing.models import Supplier

    for customer in Customer.objects.exclude(opening_due=ZERO):
        amount = _decimal(customer.opening_due)
        if amount <= ZERO:
            continue
        post_journal(
            entry_date=customer.created_at.date() if customer.created_at else timezone.localdate(),
            source_type=JournalEntry.SourceType.OPENING_BALANCE,
            source_key=f"customer_opening_due:{customer.pk}",
            source_reference=customer.customer_no,
            description=f"Opening receivable — {customer.name}",
            lines=[
                {"account": SYSTEM_ACCOUNTS["receivable"], "debit": amount, "credit": ZERO, "memo": customer.name},
                {"account": SYSTEM_ACCOUNTS["opening_equity"], "debit": ZERO, "credit": amount, "memo": "Opening balance"},
            ],
            actor=actor,
        )
    for supplier in Supplier.objects.exclude(opening_balance=ZERO):
        amount = _decimal(supplier.opening_balance)
        if amount <= ZERO:
            continue
        post_journal(
            entry_date=supplier.created_at.date() if supplier.created_at else timezone.localdate(),
            source_type=JournalEntry.SourceType.OPENING_BALANCE,
            source_key=f"supplier_opening_balance:{supplier.pk}",
            source_reference=supplier.code,
            description=f"Opening payable — {supplier.name}",
            lines=[
                {"account": SYSTEM_ACCOUNTS["opening_equity"], "debit": amount, "credit": ZERO, "memo": "Opening balance"},
                {"account": SYSTEM_ACCOUNTS["payable"], "debit": ZERO, "credit": amount, "memo": supplier.name},
            ],
            actor=actor,
        )


def backfill_accounting_history(*, actor="Accounting migration"):
    from payments.models import PaymentTransaction
    from purchasing.models import PurchaseOrder, PurchaseReceiptItem, PurchaseReturnItem
    from returns.models import SalesReturn
    from sales.models import SalesOrder
    from shipping.models import CODSettlement

    post_opening_balances(actor=actor)
    for row in PurchaseReceiptItem.objects.select_related("receipt", "purchase_item").order_by("receipt__received_date", "id"):
        post_purchase_receipt_item(row, actor=actor)
    for purchase in PurchaseOrder.objects.filter(status=PurchaseOrder.Status.RECEIVED).order_by("purchase_date", "id"):
        post_purchase_overhead(purchase, actor=actor)
    for row in PurchaseReturnItem.objects.select_related("purchase_return").order_by("purchase_return__return_date", "id"):
        post_purchase_return_item(row, actor=actor)
    for order in SalesOrder.objects.filter(status=SalesOrder.Status.COMPLETED).order_by("order_date", "id"):
        post_sales_order(order, actor=actor)
    for payment in PaymentTransaction.objects.filter(status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED]).order_by("transaction_date", "id"):
        post_payment_transaction(payment, actor=actor)
    for sales_return in SalesReturn.objects.filter(status=SalesReturn.Status.COMPLETED).order_by("completed_date", "id"):
        post_sales_return(sales_return, actor=actor)
    for settlement in CODSettlement.objects.exclude(courier_deduction=ZERO).order_by("settlement_date", "id"):
        post_cod_settlement(settlement, actor=actor)


def account_activity(account, *, start_date=None, end_date=None, as_of=None):
    qs = JournalLine.objects.select_related("entry", "account").filter(
        account=account,
        entry__status__in=[JournalEntry.Status.POSTED, JournalEntry.Status.REVERSED],
    )
    if start_date:
        qs = qs.filter(entry__entry_date__gte=start_date)
    if end_date:
        qs = qs.filter(entry__entry_date__lte=end_date)
    if as_of:
        qs = qs.filter(entry__entry_date__lte=as_of)
    return qs.order_by("entry__entry_date", "entry__id", "id")


def account_balance(account, *, as_of=None):
    qs = account_activity(account, as_of=as_of)
    totals = qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    debit = totals["debit"] or ZERO
    credit = totals["credit"] or ZERO
    return debit - credit if account.normal_balance == Account.NormalBalance.DEBIT else credit - debit


def trial_balance(*, as_of=None):
    rows = []
    total_debit = ZERO
    total_credit = ZERO
    for account in Account.objects.filter(is_active=True).order_by("code"):
        qs = account_activity(account, as_of=as_of)
        totals = qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        debit = totals["debit"] or ZERO
        credit = totals["credit"] or ZERO
        net = debit - credit
        ending_debit = net if net > ZERO else ZERO
        ending_credit = abs(net) if net < ZERO else ZERO
        total_debit += ending_debit
        total_credit += ending_credit
        rows.append({
            "account": account,
            "debit_activity": debit,
            "credit_activity": credit,
            "debit": ending_debit,
            "credit": ending_credit,
        })
    return rows, total_debit.quantize(MONEY), total_credit.quantize(MONEY)


def accounting_summary(*, as_of=None):
    accounts = {row.code: row for row in Account.objects.all()}
    def bal(code):
        account = accounts.get(code)
        return account_balance(account, as_of=as_of) if account else ZERO

    cash_equivalents = sum((bal(code) for code in ["1000", "1010", "1020", "1030", "1040", "1090"]), ZERO)
    receivable = bal(SYSTEM_ACCOUNTS["receivable"])
    inventory = bal(SYSTEM_ACCOUNTS["inventory"])
    payable = bal(SYSTEM_ACCOUNTS["payable"])
    revenue = bal(SYSTEM_ACCOUNTS["sales"]) + bal(SYSTEM_ACCOUNTS["shipping_revenue"])
    sales_returns = bal(SYSTEM_ACCOUNTS["sales_returns"])
    net_revenue = revenue - sales_returns
    expenses = ZERO
    for account in Account.objects.filter(account_type=Account.Type.EXPENSE, is_active=True):
        expenses += account_balance(account, as_of=as_of)
    net_profit = net_revenue - expenses
    return {
        "cash_equivalents": cash_equivalents,
        "receivable": receivable,
        "inventory": inventory,
        "payable": payable,
        "revenue": revenue,
        "sales_returns": sales_returns,
        "net_revenue": net_revenue,
        "expenses": expenses,
        "cogs": bal(SYSTEM_ACCOUNTS["cogs"]),
        "courier_fees": bal(SYSTEM_ACCOUNTS["courier_fees"]),
        "net_profit": net_profit,
    }

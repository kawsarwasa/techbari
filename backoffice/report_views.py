import csv
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify

from reports.after_sales import AFTER_SALES_REPORT_KEYS, AFTER_SALES_TABS, build_after_sales_report
from reports.financial import FINANCIAL_REPORT_KEYS, FINANCIAL_TABS, build_financial_report
from reports.services import REPORT_TABS, build_sales_profit_report
from reports.stock_purchase import OPERATIONAL_REPORT_KEYS, OPERATIONAL_TABS, build_stock_purchase_report
from store_settings.models import StoreSettings

from .context import page_context


ALL_REPORT_TABS = [*REPORT_TABS, *OPERATIONAL_TABS, *AFTER_SALES_TABS, *FINANCIAL_TABS]
NON_SALES_REPORT_KEYS = OPERATIONAL_REPORT_KEYS | AFTER_SALES_REPORT_KEYS | FINANCIAL_REPORT_KEYS


def reports(request):
    requested_report = str(request.GET.get("report") or "sales").strip().lower()
    if requested_report in OPERATIONAL_REPORT_KEYS:
        report = build_stock_purchase_report(request.GET)
    elif requested_report in AFTER_SALES_REPORT_KEYS:
        report = build_after_sales_report(request.GET)
    elif requested_report in FINANCIAL_REPORT_KEYS:
        report = build_financial_report(request.GET)
    else:
        report = build_sales_profit_report(request.GET)

    filters = report["filters"]
    report.setdefault("show_channel_filter", requested_report not in NON_SALES_REPORT_KEYS)
    report.setdefault("show_warehouse_filter", False)
    report.setdefault("show_movement_filter", False)
    report.setdefault("warehouse_choices", [])
    report.setdefault("movement_choices", [])
    report.setdefault("extra_filters", [])
    report.setdefault("date_scope_label", "Range")
    report.setdefault("empty_message", "No completed sales found for this filter.")

    export_format = str(request.GET.get("export") or "").strip().lower()
    if export_format == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"techbari-{report['report_key']}-{filters['date_from']}-{filters['date_to']}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(report["csv_headers"])
        writer.writerows(report["csv_rows"])
        return response

    if export_format == "pdf":
        from reports.pdf_export import build_report_pdf

        store = StoreSettings.get_solo()
        pdf_bytes = build_report_pdf(report, store)
        filename_base = slugify(f"{store.store_name}-{report['report_key']}") or "business-report"
        filename = f"{filename_base}-{filters['date_from']}-{filters['date_to']}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response

    base_url = reverse("backoffice:reports")
    common = {
        "date_from": filters["date_from"].isoformat(),
        "date_to": filters["date_to"].isoformat(),
    }
    for key in ("channel", "warehouse", "movement_type"):
        value = filters.get(key)
        if value not in (None, ""):
            common[key] = str(value)
    for extra_filter in report["extra_filters"]:
        key = extra_filter["name"]
        value = filters.get(key)
        if value not in (None, ""):
            common[key] = str(value)

    report_tabs = []
    for key, label in ALL_REPORT_TABS:
        params = {**common, "report": key}
        report_tabs.append({"key": key, "label": label, "url": f"{base_url}?{urlencode(params)}"})

    csv_params = {**common, "report": report["report_key"], "export": "csv"}
    pdf_params = {**common, "report": report["report_key"], "export": "pdf"}
    context = page_context("reports")
    context.update(report)
    context.update({
        "report_tabs": report_tabs,
        "export_csv_url": f"{base_url}?{urlencode(csv_params)}",
        "export_pdf_url": f"{base_url}?{urlencode(pdf_params)}",
        "reset_url": f"{base_url}?{urlencode({'report': report['report_key']})}",
    })
    return render(request, "backoffice/pages/reports/reports.html", context)

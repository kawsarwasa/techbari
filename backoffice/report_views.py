import csv
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from reports.services import REPORT_TABS, build_sales_profit_report
from reports.stock_purchase import OPERATIONAL_REPORT_KEYS, OPERATIONAL_TABS, build_stock_purchase_report

from .context import page_context


ALL_REPORT_TABS = [*REPORT_TABS, *OPERATIONAL_TABS]


def reports(request):
    requested_report = str(request.GET.get("report") or "sales").strip().lower()
    if requested_report in OPERATIONAL_REPORT_KEYS:
        report = build_stock_purchase_report(request.GET)
    else:
        report = build_sales_profit_report(request.GET)

    filters = report["filters"]
    report.setdefault("show_channel_filter", requested_report not in OPERATIONAL_REPORT_KEYS)
    report.setdefault("show_warehouse_filter", False)
    report.setdefault("show_movement_filter", False)
    report.setdefault("warehouse_choices", [])
    report.setdefault("movement_choices", [])
    report.setdefault("date_scope_label", "Range")
    report.setdefault("empty_message", "No completed sales found for this filter.")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"techbari-{report['report_key']}-{filters['date_from']}-{filters['date_to']}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(report["csv_headers"])
        writer.writerows(report["csv_rows"])
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

    report_tabs = []
    for key, label in ALL_REPORT_TABS:
        params = {**common, "report": key}
        report_tabs.append({"key": key, "label": label, "url": f"{base_url}?{urlencode(params)}"})

    export_params = {**common, "report": report["report_key"], "export": "csv"}
    context = page_context("reports")
    context.update(report)
    context.update({
        "report_tabs": report_tabs,
        "export_url": f"{base_url}?{urlencode(export_params)}",
        "reset_url": f"{base_url}?{urlencode({'report': report['report_key']})}",
    })
    return render(request, "backoffice/pages/reports/reports.html", context)

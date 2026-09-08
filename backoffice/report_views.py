import csv
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from reports.services import build_sales_profit_report

from .context import page_context


def reports(request):
    report = build_sales_profit_report(request.GET)
    filters = report["filters"]

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
    if filters["channel"]:
        common["channel"] = filters["channel"]

    report_tabs = []
    for tab in report["tabs"]:
        params = {**common, "report": tab["key"]}
        report_tabs.append({**tab, "url": f"{base_url}?{urlencode(params)}"})

    export_params = {**common, "report": report["report_key"], "export": "csv"}
    context = page_context("reports")
    context.update(report)
    context.update({
        "report_tabs": report_tabs,
        "export_url": f"{base_url}?{urlencode(export_params)}",
        "reset_url": f"{base_url}?{urlencode({'report': report['report_key']})}",
    })
    return render(request, "backoffice/pages/reports/reports.html", context)

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y %I:%M %p")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return str(value)


def _paragraph_text(value: Any) -> str:
    return escape(_plain(value)).replace("\n", "<br/>")


def build_report_pdf(report: dict[str, Any], store) -> bytes:
    """Render a dashboard report as a professional landscape A4 PDF."""

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    page_size = landscape(A4)
    margin_x = 14 * mm
    margin_y = 12 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=margin_x,
        leftMargin=margin_x,
        topMargin=margin_y,
        bottomMargin=15 * mm,
        title=f"{store.store_name} - {report['report_title']}",
        author=store.store_name,
        subject=report.get("report_description", "Business report"),
    )

    styles = getSampleStyleSheet()
    company_name_style = ParagraphStyle(
        "CompanyName",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=2,
    )
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=12,
        textColor=colors.HexColor("#627D98"),
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=subtitle_style,
        fontSize=8,
        leading=10.5,
    )
    table_head_style = ParagraphStyle(
        "TableHead",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9,
        textColor=colors.white,
        alignment=TA_LEFT,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.2,
        textColor=colors.HexColor("#243B53"),
    )
    table_cell_right_style = ParagraphStyle(
        "TableCellRight",
        parent=table_cell_style,
        alignment=TA_RIGHT,
    )

    story = []

    # Report branding comes only from CMS / Store Settings. Do not fall back
    # to an unrelated legacy/static logo because that can mix brands in a
    # customer-facing financial document.
    logo_flowable = None
    logo = getattr(store, "logo", None)
    if logo:
        try:
            logo.open("rb")
            logo_bytes = BytesIO(logo.read())
            logo.close()
            logo_flowable = Image(
                logo_bytes,
                width=29 * mm,
                height=14 * mm,
                kind="proportional",
            )
        except Exception:
            logo_flowable = None

    contact_parts = [
        str(part).strip()
        for part in [
            getattr(store, "address", ""),
            getattr(store, "business_email", "") or getattr(store, "support_email", ""),
            getattr(store, "support_phone", ""),
        ]
        if str(part or "").strip()
    ]
    contact_text = "  |  ".join(contact_parts)

    company_block = [
        Paragraph(_paragraph_text(store.store_name), company_name_style),
    ]
    if getattr(store, "tagline", ""):
        company_block.append(Paragraph(_paragraph_text(store.tagline), subtitle_style))
    if contact_text:
        company_block.append(Paragraph(_paragraph_text(contact_text), meta_style))

    report_brand_style = ParagraphStyle(
        "ReportBrand",
        parent=meta_style,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1677FF"),
        alignment=TA_RIGHT,
        uppercase=True,
    )
    brand_meta_style = ParagraphStyle(
        "BrandMeta",
        parent=meta_style,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#829AB1"),
    )
    right_brand_block = [
        Paragraph("BUSINESS REPORT", report_brand_style),
        Paragraph(_paragraph_text(f"Currency: {store.currency_code}"), brand_meta_style),
    ]

    if logo_flowable:
        identity = Table(
            [[logo_flowable, company_block, right_brand_block]],
            colWidths=[34 * mm, doc.width - 79 * mm, 45 * mm],
        )
    else:
        identity = Table(
            [[company_block, right_brand_block]],
            colWidths=[doc.width - 45 * mm, 45 * mm],
        )

    identity.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(identity)
    story.append(Spacer(1, 3 * mm))

    brand_divider = Table([[""]], colWidths=[doc.width], rowHeights=[0.6 * mm])
    brand_divider.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#D9E7F5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(brand_divider)
    story.append(Spacer(1, 4 * mm))

    filters = report["filters"]
    if report.get("date_scope_label") == "As of":
        period = f"As of {_plain(filters.get('date_to'))}"
    else:
        period = f"{_plain(filters.get('date_from'))} - {_plain(filters.get('date_to'))}"

    report_meta = Table([
        [
            Paragraph(_paragraph_text(report["report_title"]), title_style),
            Paragraph(_paragraph_text(period), table_cell_right_style),
        ],
        [
            Paragraph(_paragraph_text(report.get("report_description", "")), subtitle_style),
            Paragraph("", table_cell_right_style),
        ],
    ], colWidths=[doc.width * 0.73, doc.width * 0.27])
    report_meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(report_meta)
    story.append(Spacer(1, 5 * mm))

    # PDF intentionally omits the dashboard KPI cards. The exported document
    # starts directly with the detailed report table requested by the user.
    headers = list(report.get("csv_headers") or report.get("columns") or [])
    rows = list(report.get("csv_rows") or [])
    if not headers:
        headers = ["Report"]
        rows = [[report.get("empty_message", "No data available")]]

    header_row = [Paragraph(_paragraph_text(value), table_head_style) for value in headers]
    body_rows = []
    for row in rows:
        cells = []
        for value in row:
            style = table_cell_right_style if isinstance(value, (int, float, Decimal)) else table_cell_style
            cells.append(Paragraph(_paragraph_text(value), style))
        body_rows.append(cells)
    if not body_rows:
        body_rows = [[
            Paragraph(_paragraph_text(report.get("empty_message", "No data available")), table_cell_style)
        ] + [""] * (len(headers) - 1)]

    col_width = doc.width / max(len(headers), 1)
    data_table = Table(
        [header_row, *body_rows],
        colWidths=[col_width] * len(headers),
        repeatRows=1,
        hAlign="LEFT",
    )
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1677FF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(body_rows) + 1):
        background = "#FFFFFF" if row_index % 2 else "#F8FBFF"
        style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor(background)))
    data_table.setStyle(TableStyle(style_commands))
    story.append(data_table)

    generated = datetime.now().strftime("%d %b %Y %I:%M %p")

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.setLineWidth(0.4)
        canvas.line(margin_x, 10 * mm, page_size[0] - margin_x, 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#829AB1"))
        canvas.drawString(margin_x, 6.5 * mm, f"Generated {generated} | {_plain(store.store_name)}")
        canvas.drawRightString(page_size[0] - margin_x, 6.5 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

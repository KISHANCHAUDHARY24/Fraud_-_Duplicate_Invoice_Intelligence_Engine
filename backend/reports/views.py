from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import Cap, user_can
from accounts.permissions import HasCapability
from audit.models import AuditLog
from audit.services import log_action
from system_settings.services import get_setting

from .analytics import analytics
from .dashboard import dashboard_summary
from .exports import MAX_PDF_ROWS, MAX_ROWS, REPORTS
from .params import date_range
from .renderers import render_csv, render_pdf

FORMATS = {"csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}


class DashboardSummaryView(APIView):
    """GET /api/dashboard/summary/: KPIs, chart series and high-risk invoices for the current user's scope."""

    def get(self, request):
        return Response(dashboard_summary(request.user))


class AnalyticsView(APIView):
    """GET /api/analytics/?date_from=&date_to= (default: the last 12 months)."""

    permission_classes = [HasCapability.of(Cap.ANALYTICS_VIEW)]

    def get(self, request):
        date_from, date_to = date_range(request.query_params)
        return Response(analytics(request.user, date_from, date_to))


class ReportListView(APIView):
    """GET /api/reports/: the reports this user may export (for the Reports page)."""

    permission_classes = [HasCapability.of(Cap.REPORTS_EXPORT)]

    def get(self, request):
        return Response([
            {"type": report.key, "title": report.title, "description": report.description,
             "date_basis": report.date_basis, "formats": list(FORMATS)}
            for report in REPORTS.values() if user_can(request.user, report.capability)
        ])


class IgnoreFormatParameter(DefaultContentNegotiation):
    """`?format=csv|pdf` chooses the FILE type here, not DRF's renderer: errors are always JSON."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class ReportExportView(APIView):
    """GET /api/reports/{type}/?format=csv|pdf&date_from=&date_to= → a file download (audited)."""

    permission_classes = [HasCapability.of(Cap.REPORTS_EXPORT)]
    content_negotiation_class = IgnoreFormatParameter

    def get(self, request, report_type):
        report = REPORTS.get(report_type)
        if report is None:
            raise NotFound(f"Unknown report '{report_type}'. Choose one of: {', '.join(REPORTS)}.")
        if not user_can(request.user, report.capability):
            raise PermissionDenied("Your role cannot export this report.")
        file_format = request.query_params.get("format", "csv").lower()
        if file_format not in FORMATS:
            raise ValidationError({"format": "Choose csv or pdf."})
        date_from, date_to = date_range(request.query_params)

        limit = MAX_PDF_ROWS if file_format == "pdf" else MAX_ROWS
        rows = list(report.rows(request.user, date_from, date_to)[:limit + 1])
        truncated = len(rows) > limit
        rows = rows[:limit]

        # Times in the file use the business timezone (the same one the working-hours rule uses).
        zone_name = get_setting("timezone")
        with timezone.override(ZoneInfo(zone_name)):
            if file_format == "csv":
                content = render_csv(report, rows)
            else:
                content = render_pdf(report, rows, {
                    "range": f"{date_from.isoformat()} to {date_to.isoformat()}",
                    "generated": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
                    "timezone": zone_name, "by": str(request.user), "rows": len(rows), "truncated": truncated,
                })

        log_action(AuditLog.Action.REPORT_EXPORTED, user=request.user, entity_type="report", entity_id=report.key,
                   description=f"{report.title} exported as {file_format.upper()} ({date_from} to {date_to}, {len(rows)} rows)",
                   new_value={"format": file_format, "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                              "rows": len(rows), "truncated": truncated},
                   request=request)

        filename = f"expense-intelligence_{report.key}_{date_from.isoformat()}_{date_to.isoformat()}.{file_format}"
        response = HttpResponse(content, content_type=FORMATS[file_format])
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Report-Rows"] = str(len(rows))
        response["X-Report-Truncated"] = "true" if truncated else "false"
        return response

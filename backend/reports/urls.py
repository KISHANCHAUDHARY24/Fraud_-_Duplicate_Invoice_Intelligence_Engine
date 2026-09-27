from django.urls import path

from .views import AnalyticsView, DashboardSummaryView, ReportExportView, ReportListView

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
    path("reports/", ReportListView.as_view(), name="report-list"),
    path("reports/<slug:report_type>/", ReportExportView.as_view(), name="report-export"),
]

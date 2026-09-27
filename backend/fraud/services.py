"""
Run the ML analysis for an invoice and store the result (docs/architecture.md §6).

The HTTP call to the ML service happens OUTSIDE any database transaction, so no
database locks are held while waiting (up to ML_SERVICE_TIMEOUT seconds).
Storing the result is then one short atomic transaction.
"""

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from accounts.assignment import pick_auditor
from audit.models import AuditLog
from audit.services import log_action
from common.choices import RiskLevel
from common.exceptions import BusinessError
from invoices.models import Invoice
from notifications.models import Notification
from notifications.services import notify, notify_roles

from . import ml_client
from .context import build_analysis_payload
from .models import FraudAlert, FraudAnalysis, FraudSignal, SignalType

logger = logging.getLogger(__name__)

ALERT_LEVELS = {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}
AUDITOR_LEVELS = {RiskLevel.HIGH, RiskLevel.CRITICAL}
KNOWN_SIGNALS = {value for value, _ in SignalType.choices}
MESSAGE_LIMIT = 500


@dataclass
class AnalysisOutcome:
    ok: bool
    analysis: FraudAnalysis | None = None
    error: str = ""
    ml_skipped: bool = False     # rules ran, but the ML model was not available

    @property
    def risk_level(self):
        return self.analysis.risk_level if self.analysis else None


def analyze_invoice(invoice: Invoice, user=None, request=None) -> AnalysisOutcome:
    try:
        result = ml_client.analyze(build_analysis_payload(invoice))
    except ml_client.MLServiceError as exc:
        logger.error("Analysis of invoice %s failed: %s", invoice.pk, exc)
        Invoice.objects.filter(pk=invoice.pk).update(fraud_status=Invoice.FraudStatus.ANALYSIS_FAILED)
        invoice.fraud_status = Invoice.FraudStatus.ANALYSIS_FAILED
        log_action(AuditLog.Action.FRAUD_ANALYSIS_FAILED, user=user, entity=invoice, request=request,
                   description=f"Fraud analysis of {invoice.invoice_number} failed: {exc}")
        return AnalysisOutcome(ok=False, error=str(exc))

    analysis = store_result(invoice, result, user=user, request=request)
    return AnalysisOutcome(ok=True, analysis=analysis, ml_skipped=not result["anomaly"]["model_loaded"])


@transaction.atomic
def store_result(invoice: Invoice, result: dict, user=None, request=None) -> FraudAnalysis:
    anomaly, duplicate = result.get("anomaly") or {}, result.get("duplicate") or {}
    level = result["risk_level"]
    analysis = FraudAnalysis.objects.create(
        invoice=invoice, risk_score=result["risk_score"], risk_level=level,
        duplicate_score=duplicate.get("duplicate_score", 0), anomaly_score=anomaly.get("anomaly_score"),
        is_anomaly=bool(anomaly.get("is_anomaly")), model_version=anomaly.get("model_version") or "",
        raw_response=result,
    )

    points = {item["type"]: item["points"] for item in result["scoring"]["breakdown"]}
    related_ids = {s["related_invoice_id"] for s in result["signals"] if s.get("related_invoice_id")}
    existing = set(Invoice.objects.filter(pk__in=related_ids).values_list("pk", flat=True))
    FraudSignal.objects.bulk_create([
        FraudSignal(
            analysis=analysis, invoice=invoice, signal_type=signal["type"], severity=signal["severity"],
            points=points.get(signal["type"], 0), message=signal["message"][:MESSAGE_LIMIT],
            details=signal.get("details") or {},
            related_invoice_id=signal.get("related_invoice_id") if signal.get("related_invoice_id") in existing else None,
        )
        for signal in result["signals"] if signal["type"] in KNOWN_SIGNALS
    ])

    invoice.risk_score, invoice.risk_level = result["risk_score"], level
    invoice.fraud_status = Invoice.FraudStatus.FLAGGED if level in ALERT_LEVELS else Invoice.FraudStatus.NO_ISSUES
    invoice.save(update_fields=["risk_score", "risk_level", "fraud_status", "updated_at"])

    log_action(AuditLog.Action.FRAUD_ANALYSIS_EXECUTED, user=user, entity=invoice, request=request,
               description=f"Risk {result['risk_score']}/100 ({level}) for {invoice.invoice_number}",
               new_value={"risk_score": result["risk_score"], "risk_level": level,
                          "signals": [s["type"] for s in result["signals"]], "model_version": analysis.model_version})

    if level in ALERT_LEVELS:
        _open_or_update_alert(invoice, analysis, result, user, request)
    _notify(invoice, analysis, result)
    return analysis


def _open_or_update_alert(invoice, analysis, result, user, request):
    primary = result["scoring"]["breakdown"][0]["type"] if result["scoring"]["breakdown"] else SignalType.ML_ANOMALY
    alert = FraudAlert.objects.filter(invoice=invoice, status__in=FraudAlert.OPEN_STATUSES).first()
    if alert:
        alert.analysis, alert.primary_type, alert.severity = analysis, primary, analysis.risk_level
        alert.save(update_fields=["analysis", "primary_type", "severity", "updated_at"])
        return alert
    assignee = pick_auditor(exclude_user=invoice.submitted_by) if analysis.risk_level in AUDITOR_LEVELS else None
    alert = FraudAlert.objects.create(invoice=invoice, analysis=analysis, primary_type=primary,
                                      severity=analysis.risk_level, assigned_to=assignee)
    log_action(AuditLog.Action.FRAUD_ALERT_CREATED, user=user, entity=alert, request=request,
               description=f"{alert.get_severity_display()} alert ({alert.get_primary_type_display()}) "
                           f"for invoice {invoice.invoice_number}",
               new_value={"severity": alert.severity, "primary_type": primary,
                          "assigned_to": str(assignee) if assignee else None})
    return alert


def _notify(invoice, analysis, result):
    link = f"Invoice {invoice.invoice_number} ({invoice.vendor}) scored {analysis.risk_score}/100."
    if analysis.risk_level in AUDITOR_LEVELS:
        notify_roles(["AUDITOR", "ADMIN"], Notification.Type.HIGH_RISK_INVOICE,
                     title=f"{analysis.get_risk_level_display()} risk invoice {invoice.invoice_number}",
                     message=link + " " + " ".join(result.get("explanation", [])[:2]), invoice=invoice)
    duplicate = result.get("duplicate") or {}
    if duplicate.get("is_possible_duplicate"):
        notify([invoice.submitted_by], Notification.Type.DUPLICATE_DETECTED,
               title=f"Possible duplicate: {invoice.invoice_number}",
               message=f"{duplicate.get('duplicate_score')}% similar to invoice {duplicate.get('matched_invoice_number')}. "
                       f"It has been sent for review.", invoice=invoice)


# ---------------------------------------------------------------------------
# Alert actions (auditor)
# ---------------------------------------------------------------------------
def _alert_audit(action, alert, user, request, description, old=None, new=None):
    log_action(action, user=user, entity=alert, request=request, description=description, old_value=old, new_value=new)


@transaction.atomic
def _require_open(alert: FraudAlert, *statuses):
    if alert.status not in (statuses or FraudAlert.OPEN_STATUSES):
        raise BusinessError("INVALID_STATE_TRANSITION",
                            f"This alert is {alert.get_status_display().lower()}; it can no longer be changed.", status_code=409)


def assign_alert(alert: FraudAlert, auditor, user, request=None):
    _require_open(alert)
    old = str(alert.assigned_to) if alert.assigned_to_id else None
    alert.assigned_to = auditor
    alert.save(update_fields=["assigned_to", "updated_at"])
    _alert_audit(AuditLog.Action.ALERT_ASSIGNED, alert, user, request,
                 f"Alert on {alert.invoice.invoice_number} assigned to {auditor}", {"assigned_to": old},
                 {"assigned_to": str(auditor)})
    notify([auditor], Notification.Type.HIGH_RISK_INVOICE, title=f"Alert assigned: {alert.invoice.invoice_number}",
           message=f"You have been assigned the {alert.get_primary_type_display().lower()} alert.",
           invoice=alert.invoice, exclude=user)
    return alert


@transaction.atomic
def mark_reviewed(alert: FraudAlert, user, request=None):
    # Only an OPEN alert moves to IN_REVIEW; a closed alert must never be reopened this way.
    _require_open(alert, FraudAlert.Status.OPEN)
    old = alert.status
    alert.status = FraudAlert.Status.IN_REVIEW
    if alert.assigned_to_id is None:
        alert.assigned_to = user
    alert.save(update_fields=["status", "assigned_to", "updated_at"])
    _alert_audit(AuditLog.Action.ALERT_REVIEWED, alert, user, request,
                 f"Alert on {alert.invoice.invoice_number} marked as in review", {"status": old}, {"status": alert.status})
    return alert


def close_open_alerts(invoice: Invoice, user, note: str):
    """When a reviewer makes the final decision on an invoice, its open alert is closed."""
    FraudAlert.objects.filter(invoice=invoice, status__in=FraudAlert.OPEN_STATUSES).update(
        status=FraudAlert.Status.DISMISSED, resolution_note=note, resolved_by=user, resolved_at=timezone.now())

"""
Full invoice analysis: the orchestrator behind POST /api/v1/fraud/analyze.

    duplicate detector  ─┐
    rule engine (R2-R9) ─┼─► signals ─► risk scorer ─► score, level, ranked reasons
    Isolation Forest    ─┘   (ML is skipped with a warning if no model is loaded)

Every component can fail independently without hiding the others' results.
"""

import logging
from datetime import datetime, timezone

from schemas.analysis import AnomalySummary, DuplicateSummary, FraudAnalysisRequest, FraudAnalysisResponse
from schemas.duplicate import DuplicateCheckRequest
from schemas.fraud import RuleCheckRequest, SignalType
from schemas.invoice import InvoiceSnapshot

from . import duplicate_detector, risk_scorer, rule_engine
from .anomaly_detector import detector, to_signal
from .feature_engineering import build_features

logger = logging.getLogger("ml_service.analysis")


def _duplicate_check(request: FraudAnalysisRequest):
    config = request.config
    return duplicate_detector.check(DuplicateCheckRequest(
        invoice=InvoiceSnapshot(**request.invoice.model_dump(include=set(InvoiceSnapshot.model_fields))),
        candidates=request.duplicate_candidates,
        weights=config.duplicate_weights,
        threshold=config.duplicate_threshold,
        date_window_days=config.duplicate_date_window_days,
    ))


def analyze(request: FraudAnalysisRequest) -> FraudAnalysisResponse:
    config, invoice, warnings = request.config, request.invoice, []

    # 1. Duplicate detection
    duplicate = _duplicate_check(request)

    # 2. Rules (the duplicate score feeds rule R2)
    rule_request = RuleCheckRequest(
        invoice=invoice, vendor_context=request.vendor_context, bank=request.bank,
        recent_vendor_invoices=request.recent_vendor_invoices, config=config,
        duplicate_score=duplicate.duplicate_score, duplicate_match_id=duplicate.matched_invoice_id,
        duplicate_match_number=duplicate.matched_invoice_number,
    )
    signals = rule_engine.evaluate(rule_request)
    signals = [  # attach the detector's detailed reasons to the DUPLICATE signal for the UI
        s.model_copy(update={"details": {**s.details, "reasons": duplicate.signals,
                                         "components": duplicate.components.model_dump() if duplicate.components else None}})
        if s.type == SignalType.DUPLICATE else s
        for s in signals
    ]

    # 3. Machine learning (same features as training)
    features = build_features(invoice, request.vendor_context, request.bank, request.recent_vendor_invoices,
                              config, duplicate.duplicate_score)
    anomaly = AnomalySummary(model_loaded=detector.loaded)
    if detector.loaded:
        result = detector.score(features, threshold=config.ml_anomaly_threshold)
        anomaly = AnomalySummary(model_loaded=True, model_version=result.model_version,
                                 anomaly_score=result.anomaly_score, is_anomaly=result.is_anomaly,
                                 threshold=result.threshold, reasons=result.reasons)
        ml_signal = to_signal(result)
        if ml_signal:
            signals.append(ml_signal)
    else:
        warnings.append("ML model not loaded: the anomaly signal was skipped. Rules and duplicate detection ran normally.")

    # 4. Risk score + explanation
    scoring = risk_scorer.score(signals, config)
    order = {s.type: position for position, s in enumerate(scoring.breakdown)}
    signals.sort(key=lambda s: order[s.type])

    logger.info("Analysis invoice=%s score=%d level=%s signals=%s", invoice.id, scoring.risk_score,
                scoring.risk_level.value, [s.type.value for s in signals])
    return FraudAnalysisResponse(
        invoice_id=invoice.id,
        risk_score=scoring.risk_score,
        risk_level=scoring.risk_level.value,
        summary=scoring.summary,
        explanation=scoring.explanation,
        signals=signals,
        scoring=scoring,
        duplicate=DuplicateSummary(
            duplicate_score=duplicate.duplicate_score, is_possible_duplicate=duplicate.is_possible_duplicate,
            matched_invoice_id=duplicate.matched_invoice_id, matched_invoice_number=duplicate.matched_invoice_number,
            components=duplicate.components, reasons=duplicate.signals, candidates=duplicate.candidates,
        ),
        anomaly=anomaly,
        features=features,
        routing_hints={"above_approval_threshold": rule_engine.above_approval_threshold(invoice, config)},
        warnings=warnings,
        analyzed_at=datetime.now(timezone.utc),
    )

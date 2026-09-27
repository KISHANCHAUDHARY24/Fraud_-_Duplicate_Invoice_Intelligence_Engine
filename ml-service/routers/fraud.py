import logging

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.analysis import FraudAnalysisRequest, FraudAnalysisResponse
from schemas.common import ERROR_RESPONSES
from schemas.fraud import AnomalyResponse, RuleCheckRequest, RuleCheckResponse
from security import require_api_key
from services import fraud_detector, rule_engine
from services.anomaly_detector import ModelNotLoaded, detector, to_signal
from services.feature_engineering import build_features

logger = logging.getLogger("ml_service.fraud")

router = APIRouter(prefix="/api/v1/fraud", tags=["fraud detection"],
                   dependencies=[Depends(require_api_key)], responses=ERROR_RESPONSES)


@router.post("/analyze", response_model=FraudAnalysisResponse,
             summary="Full analysis: duplicates + rules + ML anomaly -> explainable 0-100 risk score")
def analyze(request: FraudAnalysisRequest) -> FraudAnalysisResponse:
    """
    The single call Django makes for each submitted invoice. Returns the risk score, level,
    ranked explanations, every signal with its details, the duplicate match and the ML result.
    If the ML model is not loaded, the rest still runs and `warnings` says so.
    """
    return fraud_detector.analyze(request)


def _features(request: RuleCheckRequest) -> dict[str, float]:
    return build_features(request.invoice, request.vendor_context, request.bank,
                          request.recent_vendor_invoices, request.config, request.duplicate_score)


@router.post("/rules", response_model=RuleCheckResponse,
             summary="Evaluate the rule-based fraud indicators for one invoice")
def check_rules(request: RuleCheckRequest) -> RuleCheckResponse:
    """
    Runs rules R2-R9 (docs/fraud-detection.md) and returns the signals that fired,
    the engineered features and routing hints. Signals carry a strength (0-1); turning
    them into a 0-100 risk score happens in `/api/v1/fraud/analyze` (Phase 8).
    """
    signals = rule_engine.evaluate(request)
    logger.info("Rules invoice=%s signals=%s", request.invoice.id, [s.type.value for s in signals])
    return RuleCheckResponse(
        signals=signals,
        features=_features(request),
        routing_hints={"above_approval_threshold": rule_engine.above_approval_threshold(request.invoice, request.config)},
        rules_evaluated=rule_engine.RULE_NAMES,
    )


@router.post("/anomaly", response_model=AnomalyResponse,
             summary="Isolation Forest anomaly score for one invoice, with an explanation",
             responses={503: {"description": "Model not trained/loaded yet"}})
def check_anomaly(request: RuleCheckRequest) -> AnomalyResponse:
    """
    Same request as `/rules`. The features are built by the same function used in training.
    `config.ml_anomaly_threshold` (default 0.6) decides whether the ML signal fires.
    """
    try:
        result = detector.score(_features(request), threshold=request.config.ml_anomaly_threshold)
    except ModelNotLoaded as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    logger.info("Anomaly invoice=%s score=%.3f anomaly=%s", request.invoice.id, result.anomaly_score, result.is_anomaly)
    return AnomalyResponse(model_version=result.model_version, anomaly_score=result.anomaly_score,
                           is_anomaly=result.is_anomaly, threshold=result.threshold, reasons=result.reasons,
                           top_features=result.top_features, signal=to_signal(result))

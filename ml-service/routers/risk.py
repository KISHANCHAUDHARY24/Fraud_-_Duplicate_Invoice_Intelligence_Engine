from fastapi import APIRouter, Depends

from schemas.common import ERROR_RESPONSES
from schemas.risk import RiskResult, RiskScoreRequest
from security import require_api_key
from services import risk_scorer

router = APIRouter(prefix="/api/v1/risk", tags=["risk scoring"],
                   dependencies=[Depends(require_api_key)], responses=ERROR_RESPONSES)


@router.post("/score", response_model=RiskResult,
             summary="Turn signals (type + strength) into a 0-100 risk score with explanations")
def score_signals(request: RiskScoreRequest) -> RiskResult:
    """Useful for 'what if' checks and for testing scoring settings before an Admin changes them."""
    return risk_scorer.score(request.signals, request.config)

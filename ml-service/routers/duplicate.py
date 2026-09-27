import logging

from fastapi import APIRouter, Depends

from schemas.common import ERROR_RESPONSES
from schemas.duplicate import DuplicateCheckRequest, DuplicateCheckResponse
from security import require_api_key
from services import duplicate_detector

logger = logging.getLogger("ml_service.duplicate")

router = APIRouter(prefix="/api/v1/duplicate", tags=["duplicate detection"],
                   dependencies=[Depends(require_api_key)], responses=ERROR_RESPONSES)


@router.post("/check", response_model=DuplicateCheckResponse,
             summary="Compare one invoice with candidate invoices and explain the best match")
def check_duplicate(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    result = duplicate_detector.check(request)
    logger.info("Duplicate check invoice=%s candidates=%d score=%d possible_duplicate=%s",
                request.invoice.id, result.candidates_evaluated, result.duplicate_score, result.is_possible_duplicate)
    return result

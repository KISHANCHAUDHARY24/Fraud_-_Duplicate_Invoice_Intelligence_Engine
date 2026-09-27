from fastapi import APIRouter, Depends

from schemas.common import ERROR_RESPONSES
from schemas.fraud import VendorAnalysisRequest, VendorAnalysisResponse
from security import require_api_key
from services import vendor_analyzer

router = APIRouter(prefix="/api/v1/vendor", tags=["vendor analysis"],
                   dependencies=[Depends(require_api_key)], responses=ERROR_RESPONSES)


@router.post("/analyze", response_model=VendorAnalysisResponse,
             summary="Vendor-level risk indicators (bank changes, alert history, invoice patterns)")
def analyze_vendor(request: VendorAnalysisRequest) -> VendorAnalysisResponse:
    return vendor_analyzer.analyze(request)

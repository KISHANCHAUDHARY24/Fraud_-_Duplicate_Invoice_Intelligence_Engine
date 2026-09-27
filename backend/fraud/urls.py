from rest_framework.routers import SimpleRouter

from .views import FraudAlertViewSet, FraudAnalysisViewSet

router = SimpleRouter()
router.register("fraud/alerts", FraudAlertViewSet, basename="fraud-alert")
router.register("fraud/analyses", FraudAnalysisViewSet, basename="fraud-analysis")

urlpatterns = router.urls

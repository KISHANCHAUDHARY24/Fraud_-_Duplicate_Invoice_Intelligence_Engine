from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ApprovalViewSet, PaymentViewSet, SimulatePaymentView

router = SimpleRouter()
router.register("approvals", ApprovalViewSet, basename="approval")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("payments/<int:invoice_id>/simulate/", SimulatePaymentView.as_view(), name="payment-simulate"),
] + router.urls

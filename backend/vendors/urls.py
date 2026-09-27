from rest_framework.routers import SimpleRouter

from .views import VendorViewSet

router = SimpleRouter()
router.register("vendors", VendorViewSet, basename="vendor")

urlpatterns = router.urls

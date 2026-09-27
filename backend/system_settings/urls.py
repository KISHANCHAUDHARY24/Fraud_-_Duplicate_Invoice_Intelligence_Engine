from rest_framework.routers import SimpleRouter

from .views import SystemSettingViewSet

router = SimpleRouter()
router.register("settings", SystemSettingViewSet, basename="setting")

urlpatterns = router.urls

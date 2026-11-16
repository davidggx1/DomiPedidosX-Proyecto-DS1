from rest_framework.routers import SimpleRouter

from .views import ComboViewSet, PromocionViewSet

router = SimpleRouter()
router.register("promociones", PromocionViewSet, basename="promocion")
router.register("combos", ComboViewSet, basename="combo")

urlpatterns = router.urls
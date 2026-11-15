from rest_framework.routers import SimpleRouter

from .views import PromocionViewSet

router = SimpleRouter()
router.register("promociones", PromocionViewSet, basename="promocion")

# Se incluye bajo "api/": HU-85 agregará aquí "combos".
urlpatterns = router.urls
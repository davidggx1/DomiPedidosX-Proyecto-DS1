from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SedeViewSet,
    HorarioSedeViewSet,
    FeriadoViewSet,
    CiudadViewSet,
    CapacidadSedeViewSet,
    ZonaCoberturaViewSet,
)

router = DefaultRouter()
router.register(r'sedes', SedeViewSet, basename='sede')
router.register(r'ciudades', CiudadViewSet, basename='ciudad')
router.register(r'horarios', HorarioSedeViewSet, basename='horario')
router.register(r'feriados', FeriadoViewSet, basename='feriado')
router.register(r'capacidades', CapacidadSedeViewSet, basename='capacidad')
router.register(r'zonas-cobertura', ZonaCoberturaViewSet, basename='zona-cobertura')

urlpatterns = [
    path('', include(router.urls)),
]
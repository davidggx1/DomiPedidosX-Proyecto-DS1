from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SedeViewSet

router = DefaultRouter()
router.register(r'sedes', SedeViewSet, basename='sede')

urlpatterns = [
    path('', include(router.urls)),
]
from django.urls import path

from .views import RegistroClienteView

urlpatterns = [
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
]
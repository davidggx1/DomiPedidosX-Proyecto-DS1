from django.urls import path

from .views import LoginView, RegistroClienteView, RegistroClienteView, EmpleadoManagementView

urlpatterns = [
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("login/", LoginView.as_view(), name="login"),
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("empleados/", EmpleadoManagementView.as_view(), name="gestion-empleados"),
]
from django.urls import path

from .views import LoginView, RegistroClienteView, EmpleadoManagementView
from .views import LoginPersonalView, PerfilPersonalView

urlpatterns = [
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("login/", LoginView.as_view(), name="login"),
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("empleados/", EmpleadoManagementView.as_view(), name="gestion-empleados"),
    path("login-personal/", LoginPersonalView.as_view(), name="login-personal"),
    path("perfil-personal/", PerfilPersonalView.as_view(), name="perfil-personal"),
]
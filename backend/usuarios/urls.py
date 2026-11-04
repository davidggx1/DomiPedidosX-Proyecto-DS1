from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import LoginView, RegistroClienteView, EmpleadoManagementView
from .views import DireccionEntregaViewSet, LoginPersonalView, PerfilPersonalView

router = SimpleRouter()
router.register("direcciones", DireccionEntregaViewSet, basename="direccion")

urlpatterns = [
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("login/", LoginView.as_view(), name="login"),
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("empleados/", EmpleadoManagementView.as_view(), name="gestion-empleados"),
    path("login-personal/", LoginPersonalView.as_view(), name="login-personal"),
    path("perfil-personal/", PerfilPersonalView.as_view(), name="perfil-personal"),
    path("", include(router.urls)),
]

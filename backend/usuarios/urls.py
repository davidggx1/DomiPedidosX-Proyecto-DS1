from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import LoginView, RegistroClienteView, EmpleadoManagementView
from .views import DireccionEntregaViewSet, LoginPersonalView, PerfilClienteView, PerfilPersonalView
from .repartidores import MiDisponibilidadView, RepartidoresView
from .cuentas import CuentasView, CuentaView
from .clientes import ClientesView, FichaClienteView

router = SimpleRouter()
router.register("direcciones", DireccionEntregaViewSet, basename="direccion")

urlpatterns = [
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("login/", LoginView.as_view(), name="login"),
    path("registro/", RegistroClienteView.as_view(), name="registro-cliente"),
    path("empleados/", EmpleadoManagementView.as_view(), name="gestion-empleados"),
    path("login-personal/", LoginPersonalView.as_view(), name="login-personal"),
    path("perfil-personal/", PerfilPersonalView.as_view(), name="perfil-personal"),
    path("perfil/", PerfilClienteView.as_view(), name="perfil-cliente"),
    path("repartidor/disponibilidad/", MiDisponibilidadView.as_view(), name="repartidor-disponibilidad"),
    path("repartidores/", RepartidoresView.as_view(), name="repartidores"),
    path("cuentas/", CuentasView.as_view(), name="cuentas"),
    path("cuentas/<int:pk>/", CuentaView.as_view(), name="cuenta"),
    path("clientes/", ClientesView.as_view(), name="clientes"),
    path("clientes/<int:pk>/", FichaClienteView.as_view(), name="cliente-ficha"),
    path("", include(router.urls)),
]

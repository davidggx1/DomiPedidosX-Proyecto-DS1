from datetime import datetime
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from usuarios.roles import ADMINISTRADOR
from pedidos.models import EstadoPedido, Pedido
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Empleado, Repartidor

User = get_user_model()


@pytest.mark.django_db
class TestHU68FiltrosHistorialPedidos:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

        # Administrador
        grupo_admin, _ = Group.objects.get_or_create(name=ADMINISTRADOR)
        self.admin = User.objects.create_user(
            username="admin_hu68",
            email="admin_hu68@domipedidos.com",
            password="Password123!",
            is_staff=True,
        )
        self.admin.groups.add(grupo_admin)
        self.client.force_authenticate(user=self.admin)

        # Sedes y zonas
        ciudad = Ciudad.objects.create(nombre="Cali")
        self.sede_norte = Sede.objects.create(
            ciudad=ciudad, nombre="Sede Norte", direccion="Av 6N", activa=True,
            latitud=3.48, longitud=-76.52, barrio="Granada", telefono="3001111111", correo="norte@test.com",
        )
        self.sede_sur = Sede.objects.create(
            ciudad=ciudad, nombre="Sede Sur", direccion="Calle 5", activa=True,
            latitud=3.39, longitud=-76.54, barrio="Unicentro", telefono="3002222222", correo="sur@test.com",
        )
        self.zona_norte = ZonaCobertura.objects.create(
            sede=self.sede_norte, nombre="Zona Granada", radio=3.0,
            centro_latitud=3.48, centro_longitud=-76.52,
            tarifa_domicilio=4000, tiempo_estimado=25, pedido_minimo=10000, activo=True,
        )

        # Repartidor
        user_rep = User.objects.create_user(
            username="rep_hu68", email="rep_hu68@test.com", password="Password123!"
        )
        emp_rep = Empleado.objects.create(
            usuario=user_rep,
            sede=self.sede_norte,
            nombres="Carlos",
            apellidos="Pérez",
        )
        self.repartidor = Repartidor.objects.create(empleado=emp_rep)

        # Pedidos de prueba
        self.p1 = Pedido.objects.create(
            numero_pedido="PED-1001", sede=self.sede_norte, estado=EstadoPedido.ENTREGADO,
            repartidor=self.repartidor, zona_cobertura=self.zona_norte,
        )
        self.p2 = Pedido.objects.create(
            numero_pedido="PED-1002", sede=self.sede_norte, estado=EstadoPedido.CANCELADO,
            zona_cobertura=self.zona_norte,
        )
        self.p3 = Pedido.objects.create(
            numero_pedido="PED-1003", sede=self.sede_sur, estado=EstadoPedido.ENTREGADO,
        )

        # Ajustar fecha_creacion (auto_now_add requiere .update)
        tz = timezone.get_current_timezone()
        Pedido.objects.filter(pk=self.p1.pk).update(fecha_creacion=timezone.make_aware(datetime(2026, 11, 10, 12, 0), tz))
        Pedido.objects.filter(pk=self.p2.pk).update(fecha_creacion=timezone.make_aware(datetime(2026, 11, 12, 15, 0), tz))
        Pedido.objects.filter(pk=self.p3.pk).update(fecha_creacion=timezone.make_aware(datetime(2026, 11, 13, 18, 0), tz))

    def test_criterio1_filtros_combinables(self):
        """Combina sede, estado, repartidor, zona y rango de fechas."""
        response = self.client.get(
            "/api/pedidos/historial/",
            {
                "sede": self.sede_norte.id,
                "estado": EstadoPedido.ENTREGADO,
                "repartidor": self.repartidor.id,
                "zona": self.zona_norte.id,
                "fecha_inicio": "2026-11-10",
                "fecha_fin": "2026-11-11",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["numero_pedido"] == "PED-1001"

    def test_criterio2_contador_y_paginacion_conserva_filtros(self):
        """Muestra el contador exacto de coincidencias y pagina manteniendo los filtros activos."""
        response_p1 = self.client.get(
            "/api/pedidos/historial/",
            {"sede": self.sede_norte.id, "tamano": 1, "page": 1},
        )
        assert response_p1.status_code == status.HTTP_200_OK
        assert response_p1.data["count"] == 2
        assert len(response_p1.data["results"]) == 1
        assert response_p1.data["results"][0]["numero_pedido"] == "PED-1002"

        response_p2 = self.client.get(
            "/api/pedidos/historial/",
            {"sede": self.sede_norte.id, "tamano": 1, "page": 2},
        )
        assert response_p2.status_code == status.HTTP_200_OK
        assert response_p2.data["count"] == 2
        assert response_p2.data["results"][0]["numero_pedido"] == "PED-1001"

    def test_criterio3_sin_filtros_retorna_todos(self):
        """Sin parámetros devuelve la lista completa de pedidos."""
        response = self.client.get("/api/pedidos/historial/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
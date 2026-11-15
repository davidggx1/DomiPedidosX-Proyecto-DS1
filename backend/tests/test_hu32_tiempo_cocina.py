from datetime import datetime, timedelta
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from pedidos.models import EstadoPedido, HistorialEstadoPedido, Pedido
from sedes.models import Ciudad, Sede
from usuarios.models import Empleado
from usuarios.roles import COCINA

User = get_user_model()


@pytest.mark.django_db
class TestHU32TiempoTranscurridoCocina:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        ciudad = Ciudad.objects.create(nombre="Cali")
        self.sede = Sede.objects.create(
            ciudad=ciudad, nombre="Sede Cocina", direccion="Calle 10", activa=True,
            latitud=3.45, longitud=-76.53, barrio="Centro", telefono="3009999999", correo="cocina@test.com",
        )
        grupo_cocina, _ = Group.objects.get_or_create(name=COCINA)
        self.user_cocina = User.objects.create_user(
            username="cocinero_hu32", email="cocina_hu32@test.com", password="Password123!"
        )
        self.user_cocina.groups.add(grupo_cocina)
        Empleado.objects.create(
            usuario=self.user_cocina, sede=self.sede, nombres="Luis", apellidos="Gómez"
        )
        self.client.force_authenticate(user=self.user_cocina)

    def test_tablero_ordena_mas_antiguo_arriba_y_registra_listo_en(self):
        ahora = timezone.now()
        p_nuevo = Pedido.objects.create(
            numero_pedido="PED-NEW", sede=self.sede, estado=EstadoPedido.RECIBIDO
        )
        p_antiguo = Pedido.objects.create(
            numero_pedido="PED-OLD", sede=self.sede, estado=EstadoPedido.RECIBIDO
        )
        Pedido.objects.filter(pk=p_nuevo.pk).update(fecha_creacion=ahora - timedelta(minutes=3))
        Pedido.objects.filter(pk=p_antiguo.pk).update(fecha_creacion=ahora - timedelta(minutes=18))

        # 1. Verificar orden: más antiguo arriba
        resp = self.client.get("/api/pedidos/cocina/tablero/")
        assert resp.status_code == status.HTTP_200_OK
        recibidos = resp.data["recibido"]
        assert [p["numero_pedido"] for p in recibidos] == ["PED-OLD", "PED-NEW"]
        assert recibidos[0]["listo_en"] is None

        # 2. Avanzar a en_preparacion y luego a listo_despacho: debe registrar listo_en para detener el timer
        self.client.patch(f"/api/pedidos/{p_antiguo.id}/estado/", {"estado": EstadoPedido.EN_PREPARACION})
        self.client.patch(f"/api/pedidos/{p_antiguo.id}/estado/", {"estado": EstadoPedido.LISTO_DESPACHO})

        resp_final = self.client.get("/api/pedidos/cocina/tablero/")
        listos = resp_final.data["listo_despacho"]
        assert len(listos) == 1
        assert listos[0]["numero_pedido"] == "PED-OLD"
        assert listos[0]["listo_en"] is not None
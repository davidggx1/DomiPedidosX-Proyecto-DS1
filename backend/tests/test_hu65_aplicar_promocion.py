from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from inventario.models import InventarioProducto
from menu.models import CategoriaMenu, Producto
from pedidos.models import EstadoPedido, Pedido
from promociones.models import ConsumoCupoPromocion, Promocion, TipoDescuento
from sedes.models import Ciudad, Sede, ZonaCobertura
from usuarios.models import Cliente, DireccionEntrega

User = get_user_model()


@pytest.mark.django_db
class TestHU65AplicarPromocionCarrito:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        hoy = timezone.localdate()

        ciudad = Ciudad.objects.create(nombre="Palmira")
        self.sede = Sede.objects.create(
            ciudad=ciudad, nombre="Sede Centro", direccion="Calle 30", activa=True,
            latitud=3.53, longitud=-76.30, barrio="Centro", telefono="3001112233", correo="sede@test.com",
        )
        ZonaCobertura.objects.create(
            sede=self.sede, nombre="Zona 1", centro_latitud=3.53, centro_longitud=-76.30,
            radio=5.0, tarifa_domicilio=Decimal("4000.00"), pedido_minimo=Decimal("10000.00"),
            tiempo_estimado=30, activo=True,
        )

        categoria = CategoriaMenu.objects.create(nombre="Pizzas", activa=True)
        self.producto = Producto.objects.create(
            categoria=categoria, nombre="Pizza Pepperoni", precio_base=Decimal("40000.00"),
            tiempo_preparacion=15, activo=True,
        )
        InventarioProducto.objects.create(
            sede=self.sede, producto=self.producto, stock_actual=50, disponible=True
        )

        self.promo_vigente = Promocion.objects.create(
            sede=self.sede,
            nombre="DOMI20",
            descripcion="20% de descuento",
            tipo_descuento=TipoDescuento.PORCENTAJE,
            valor=Decimal("20.00"),
            fecha_inicio=hoy - timedelta(days=1),
            fecha_fin=hoy + timedelta(days=5),
            condiciones="Compra mínima $30.000",
            activa=True,
            cupo_max_diario=2,
        )
        self.promo_vencida = Promocion.objects.create(
            sede=self.sede,
            nombre="VENCIDA10",
            tipo_descuento=TipoDescuento.PORCENTAJE,
            valor=Decimal("10.00"),
            fecha_inicio=hoy - timedelta(days=10),
            fecha_fin=hoy - timedelta(days=1),
            activa=True,
        )
        self.promo_inactiva = Promocion.objects.create(
            sede=self.sede,
            nombre="INACTIVA5000",
            tipo_descuento=TipoDescuento.VALOR_FIJO,
            valor=Decimal("5000.00"),
            fecha_inicio=hoy - timedelta(days=1),
            fecha_fin=hoy + timedelta(days=5),
            activa=False,
        )

        self.url_resumen = f"/api/menu/sedes/{self.sede.id}/carrito/resumen/"

    def test_criterio1_aplica_cupon_vigente_y_recalcula_total(self):
        payload = {
            "lineas": [{"producto": self.producto.id, "cantidad": 1}],
            "codigo_promocion": "domi20",
        }
        resp = self.client.post(self.url_resumen, payload, format="json")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["subtotal"] == "40000.00"
        assert resp.data["descuento"] == "8000.00"
        assert resp.data["costo_domicilio"] == "4000.00"
        assert resp.data["total"] == "36000.00"
        assert resp.data["promocion"]["nombre"] == "DOMI20"

    def test_criterio2_rechaza_vencidos_inactivos_y_condicion_minima_con_causa(self):
        # Cupón vencido
        r1 = self.client.post(
            self.url_resumen,
            {"lineas": [{"producto": self.producto.id, "cantidad": 1}], "codigo_promocion": "VENCIDA10"},
            format="json",
        )
        assert r1.status_code == status.HTTP_400_BAD_REQUEST
        assert "venció" in str(r1.data["codigo_promocion"]).lower()

        # Cupón inactivo
        r2 = self.client.post(
            self.url_resumen,
            {"lineas": [{"producto": self.producto.id, "cantidad": 1}], "codigo_promocion": "INACTIVA5000"},
            format="json",
        )
        assert r2.status_code == status.HTTP_400_BAD_REQUEST
        assert "activo" in str(r2.data["codigo_promocion"]).lower()

        # No cumple compra mínima ($20.000 < $30.000)
        prod_barato = Producto.objects.create(
            categoria=self.producto.categoria, nombre="Gaseosa", precio_base=Decimal("20000.00"),
            tiempo_preparacion=2, activo=True,
        )
        InventarioProducto.objects.create(
            sede=self.sede, producto=prod_barato, stock_actual=50, disponible=True
        )
        r3 = self.client.post(
            self.url_resumen,
            {"lineas": [{"producto": prod_barato.id, "cantidad": 1}], "codigo_promocion": "DOMI20"},
            format="json",
        )
        assert r3.status_code == status.HTTP_400_BAD_REQUEST
        assert "mínima" in str(r3.data["codigo_promocion"]).lower()

    def test_criterio3_rechaza_cupon_con_bolsa_diaria_agotada(self):
        # Agotar los 2 cupos diarios de DOMI20
        for idx in range(2):
            ped = Pedido.objects.create(
                numero_pedido=f"P-TEST-{idx}", sede=self.sede, estado=EstadoPedido.RECIBIDO
            )
            ConsumoCupoPromocion.objects.create(promocion=self.promo_vigente, pedido=ped)

        resp = self.client.post(
            self.url_resumen,
            {"lineas": [{"producto": self.producto.id, "cantidad": 1}], "codigo_promocion": "DOMI20"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "agotó" in str(resp.data["codigo_promocion"]).lower()

    def test_criterio4_remover_cupon_restaura_precio_original(self):
        resp = self.client.post(
            self.url_resumen,
            {"lineas": [{"producto": self.producto.id, "cantidad": 1}], "codigo_promocion": ""},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["descuento"] == "0.00"
        assert resp.data["promocion"] is None
        assert resp.data["total"] == "44000.00"

    def test_criterio5_confirmar_pedido_aplica_una_promocion_y_descuenta_bolsa(self):
        user = User.objects.create_user(
            username="cliente_hu65", email="cliente_hu65@test.com", password="Password123!"
        )
        cliente = Cliente.objects.create(
            usuario=user,
            nombres="Ana",
            apellidos="Pérez",
            celular="3005556677",
            fecha_nacimiento=date(1995, 5, 15),
        )
        direccion = DireccionEntrega.objects.create(
            cliente=cliente,
            ciudad=self.sede.ciudad,
            alias="Casa",
            direccion="Calle 30 # 20-10",
            barrio="Centro",
            latitud=3.53,
            longitud=-76.30,
            activa=True,
        )
        self.client.force_authenticate(user=user)

        resp = self.client.post(
            "/api/pedidos/confirmar/",
            {
                "sede_id": self.sede.id,
                "direccion_id": direccion.id,
                "metodo_pago": "efectivo",
                "codigo_promocion": "DOMI20",
                "items": [{"producto_id": self.producto.id, "cantidad": 1}],
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert Decimal(resp.data["factura"]["valor_descuento"]) == Decimal("8000.00")
        assert Decimal(resp.data["factura"]["total"]) == Decimal("36000.00")
        assert ConsumoCupoPromocion.objects.filter(promocion=self.promo_vigente).count() == 1
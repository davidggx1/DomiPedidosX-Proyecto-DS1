"""
Uso:

    python backend/manage.py seed_datos
    python backend/manage.py seed_datos --admin-password "OtraClave#2026"

Es idempotente: se puede ejecutar varias veces sin duplicar registros.
Solo para bases locales. Nunca ejecutarlo contra Supabase.
"""
import os
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import InventarioProducto
from menu.models import (
    Adicion,
    CategoriaMenu,
    Insumo,
    Producto,
    ProductoAdicion,
    ProductoInsumo,
    ProductoTamano,
)
from sedes.models import Ciudad, DiaSemana, HorarioSede, Sede
from usuarios.models import Usuario

# Nombres de los grupos (roles). Deben coincidir con los que use la Tarea 3
# (autenticación y permisos por rol).
ROLES = ["administrador", "operador", "cocina", "repartidor", "cliente"]

ADMIN_EMAIL = "admin@domipedidosx.local"
ADMIN_PASSWORD_POR_DEFECTO = "AdminLocal#2026"

SEDES = [
    {
        "nombre": "Sede Centro",
        "direccion": "Cra 5 # 12-30",
        "barrio": "San Pedro",
        "latitud": 3.4516,
        "longitud": -76.5320,
        "telefono": "6023000001",
        "correo": "centro@domipedidosx.local",
    },
    {
        "nombre": "Sede Sur",
        "direccion": "Cra 100 # 16-20",
        "barrio": "Ciudad Jardín",
        "latitud": 3.3700,
        "longitud": -76.5320,
        "telefono": "6023000002",
        "correo": "sur@domipedidosx.local",
    },
]

# "Postres" queda sin productos a propósito: sirve para probar el mensaje
# de categoría vacía (HU-18).
CATEGORIAS = ["Hamburguesas", "Pizzas", "Bebidas", "Postres"]

# nombre: unidad de medida
INSUMOS = {
    "Pan": "unidad",
    "Carne de res": "unidad",
    "Queso": "g",
    "Tocineta": "g",
    "Lechuga": "g",
    "Tomate": "g",
    "Cebolla": "g",
    "Masa de pizza": "unidad",
    "Salsa de tomate": "ml",
    "Pepperoni": "g",
    "Champiñones": "g",
    "Limón": "unidad",
}

PRODUCTOS = [
    {
        "nombre": "Hamburguesa clásica",
        "categoria": "Hamburguesas",
        "descripcion": "Carne de res, queso, lechuga, tomate y cebolla.",
        "precio_base": "18000",
        "tiempo_preparacion": 15,
        "tamanos": [],
        # (insumo, cantidad, es_excluible)
        "ingredientes": [
            ("Pan", "1", False),
            ("Carne de res", "1", False),
            ("Queso", "30", True),
            ("Lechuga", "15", True),
            ("Tomate", "20", True),
            ("Cebolla", "10", True),
        ],
        "adiciones": ["Queso extra", "Tocineta extra"],
    },
    {
        "nombre": "Hamburguesa doble",
        "categoria": "Hamburguesas",
        "descripcion": "Doble carne de res, doble queso y tocineta.",
        "precio_base": "26000",
        "tiempo_preparacion": 20,
        "tamanos": [],
        "ingredientes": [
            ("Pan", "1", False),
            ("Carne de res", "2", False),
            ("Queso", "60", True),
            ("Tocineta", "30", True),
        ],
        "adiciones": ["Queso extra", "Tocineta extra"],
    },
    {
        "nombre": "Pizza pepperoni",
        "categoria": "Pizzas",
        "descripcion": "Salsa de tomate, queso y pepperoni.",
        "precio_base": "32000",
        "tiempo_preparacion": 25,
        # (nombre, diferencia sobre el precio base)
        "tamanos": [("Personal", "0"), ("Mediana", "0"), ("Familiar", "12000")],
        "ingredientes": [
            ("Masa de pizza", "1", False),
            ("Salsa de tomate", "80", False),
            ("Queso", "120", False),
            ("Pepperoni", "60", True),
        ],
        "adiciones": ["Queso extra", "Champiñones"],
    },
    {
        "nombre": "Pizza margarita",
        "categoria": "Pizzas",
        "descripcion": "Salsa de tomate, queso y tomate.",
        "precio_base": "28000",
        "tiempo_preparacion": 25,
        "tamanos": [("Personal", "0"), ("Mediana", "0"), ("Familiar", "10000")],
        "ingredientes": [
            ("Masa de pizza", "1", False),
            ("Salsa de tomate", "80", False),
            ("Queso", "120", False),
            ("Tomate", "40", True),
        ],
        "adiciones": ["Queso extra", "Champiñones"],
    },
    {
        "nombre": "Gaseosa",
        "categoria": "Bebidas",
        "descripcion": "Gaseosa fría.",
        "precio_base": "5000",
        "tiempo_preparacion": 1,
        "tamanos": [("350 ml", "0"), ("1,5 L", "4000")],
        "ingredientes": [],
        "adiciones": [],
    },
    {
        "nombre": "Limonada natural",
        "categoria": "Bebidas",
        "descripcion": "Limonada recién preparada.",
        "precio_base": "6000",
        "tiempo_preparacion": 5,
        "tamanos": [],
        "ingredientes": [("Limón", "2", False)],
        "adiciones": [],
    },
]

# nombre: (insumo que consume, precio)
ADICIONES = {
    "Queso extra": ("Queso", "3000"),
    "Tocineta extra": ("Tocineta", "4000"),
    "Champiñones": ("Champiñones", "2500"),
}

# Producto marcado como NO disponible en una sede, para probar la etiqueta
# "No disponible" y el aislamiento entre sedes (HU-13 y HU-18).
NO_DISPONIBLES = {("Sede Sur", "Limonada natural")}


class Command(BaseCommand):
    help = "Crea datos de ejemplo: administrador, roles, sedes, categorías y productos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-password",
            default=os.getenv("SEED_ADMIN_PASSWORD", ADMIN_PASSWORD_POR_DEFECTO),
            help="Contraseña del administrador de prueba.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._crear_roles()
        self._crear_admin(options["admin_password"])
        sedes = self._crear_sedes()
        categorias = self._crear_categorias()
        insumos = self._crear_insumos()
        adiciones = self._crear_adiciones(insumos)
        productos = self._crear_productos(categorias, insumos, adiciones)
        self._crear_inventario(sedes, productos)

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados."))
        self.stdout.write(f"Administrador: {ADMIN_EMAIL}")

    def _crear_roles(self):
        for nombre in ROLES:
            Group.objects.get_or_create(name=nombre)

    def _crear_admin(self, password):
        admin, creado = Usuario.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={"username": ADMIN_EMAIL, "is_staff": True, "is_superuser": True},
        )
        if creado:
            admin.set_password(password)
            admin.save()
        admin.groups.add(Group.objects.get(name="administrador"))

    def _crear_sedes(self):
        ciudad, _ = Ciudad.objects.get_or_create(nombre="Cali")
        sedes = {}
        for datos in SEDES:
            datos = dict(datos)
            nombre = datos.pop("nombre")
            sede, _ = Sede.objects.get_or_create(
                nombre=nombre, defaults={"ciudad": ciudad, **datos}
            )
            for dia in DiaSemana.values:
                HorarioSede.objects.get_or_create(
                    sede=sede,
                    dia_semana=dia,
                    hora_apertura="11:00",
                    hora_cierre="22:00",
                )
            sedes[nombre] = sede
        return sedes

    def _crear_categorias(self):
        return {
            nombre: CategoriaMenu.objects.get_or_create(nombre=nombre)[0]
            for nombre in CATEGORIAS
        }

    def _crear_insumos(self):
        return {
            nombre: Insumo.objects.get_or_create(
                nombre=nombre, defaults={"unidad_medida": unidad}
            )[0]
            for nombre, unidad in INSUMOS.items()
        }

    def _crear_adiciones(self, insumos):
        adiciones = {}
        for nombre, (insumo, precio) in ADICIONES.items():
            adiciones[nombre], _ = Adicion.objects.get_or_create(
                nombre=nombre,
                defaults={"insumo": insumos[insumo], "precio": Decimal(precio)},
            )
        return adiciones

    def _crear_productos(self, categorias, insumos, adiciones):
        productos = {}
        for datos in PRODUCTOS:
            producto, _ = Producto.objects.get_or_create(
                nombre=datos["nombre"],
                categoria=categorias[datos["categoria"]],
                defaults={
                    "descripcion": datos["descripcion"],
                    "precio_base": Decimal(datos["precio_base"]),
                    "tiempo_preparacion": datos["tiempo_preparacion"],
                },
            )
            for nombre, diferencia in datos["tamanos"]:
                ProductoTamano.objects.get_or_create(
                    producto=producto,
                    nombre=nombre,
                    defaults={"precio_adicional": Decimal(diferencia)},
                )
            for insumo, cantidad, excluible in datos["ingredientes"]:
                ProductoInsumo.objects.get_or_create(
                    producto=producto,
                    insumo=insumos[insumo],
                    defaults={
                        "cantidad_necesaria": Decimal(cantidad),
                        "es_excluible": excluible,
                    },
                )
            for nombre in datos["adiciones"]:
                ProductoAdicion.objects.get_or_create(
                    producto=producto, adicion=adiciones[nombre]
                )
            productos[datos["nombre"]] = producto
        return productos

    def _crear_inventario(self, sedes, productos):
        for nombre_sede, sede in sedes.items():
            for nombre_producto, producto in productos.items():
                InventarioProducto.objects.get_or_create(
                    sede=sede,
                    producto=producto,
                    defaults={
                        "stock_actual": 50,
                        "stock_minimo": 5,
                        "disponible": (nombre_sede, nombre_producto) not in NO_DISPONIBLES,
                    },
                )

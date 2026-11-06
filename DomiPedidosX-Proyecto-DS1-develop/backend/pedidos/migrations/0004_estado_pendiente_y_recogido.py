from django.db import migrations, models

ESTADOS = [
    ("pendiente_aprobacion", "Pendiente de aprobación"),
    ("recibido", "Recibido"),
    ("en_preparacion", "En preparación"),
    ("listo_despacho", "Listo para despacho"),
    ("recogido", "Recogido"),
    ("en_camino", "En camino"),
    ("entregado", "Entregado"),
    ("cancelado", "Cancelado"),
]


class Migration(migrations.Migration):
    """HU-31: agrega los estados "Pendiente de aprobación" (HU-23/28) y "Recogido" (HU-45)."""

    dependencies = [
        ("pedidos", "0003_pedido_entrega_indicaciones"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pedido",
            name="estado",
            field=models.CharField(choices=ESTADOS, default="recibido", max_length=20),
        ),
        migrations.AlterField(
            model_name="historialestadopedido",
            name="estado",
            field=models.CharField(choices=ESTADOS, max_length=20),
        ),
    ]

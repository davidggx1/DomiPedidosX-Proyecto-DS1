import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """HU-30: guarda los ingredientes que el cliente pidió quitar de cada plato."""

    dependencies = [
        ("menu", "0003_producto_tamano_precio"),
        ("pedidos", "0004_estado_pendiente_y_recogido"),
    ]

    operations = [
        migrations.CreateModel(
            name="DetallePedidoExclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre_insumo", models.CharField(max_length=100)),
                (
                    "detalle_pedido",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exclusiones",
                        to="pedidos.detallepedido",
                    ),
                ),
                (
                    "insumo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exclusiones_pedido",
                        to="menu.insumo",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("detalle_pedido", "insumo"), name="detalle_exclusion_unica")
                ],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0002_producto_imagen"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="productotamano",
            constraint=models.CheckConstraint(
                condition=models.Q(("precio_adicional__gte", 0)),
                name="producto_tamano_precio_no_negativo",
            ),
        ),
    ]

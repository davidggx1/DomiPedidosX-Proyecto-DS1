from django.db import migrations, models


class Migration(migrations.Migration):
    """HU-41: el repartidor arranca "No disponible" hasta que active su jornada."""

    dependencies = [
        ("usuarios", "0007_direccion_indicaciones"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repartidor",
            name="disponible",
            field=models.BooleanField(default=False),
        ),
    ]

import pytest
from django.db import connection


@pytest.mark.django_db
def test_conexion_a_la_base_de_datos():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
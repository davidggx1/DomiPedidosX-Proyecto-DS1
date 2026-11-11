import pytest

from pedidos import capacidad


@pytest.fixture(autouse=True)
def sin_control_de_capacidad(request, monkeypatch):
    """
    HU-61 blocks orders when a sede has no capacity slot. The older tests do not
    configure one, so the check is off for them. Tests that need it use
    @pytest.mark.capacidad
    """
    if request.node.get_closest_marker("capacidad"):
        return
    monkeypatch.setattr(capacidad, "validar_cupo_nuevo_pedido", lambda *a, **k: None)

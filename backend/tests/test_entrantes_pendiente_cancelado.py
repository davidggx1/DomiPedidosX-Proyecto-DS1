"""Un pedido pendiente que se cancela sale de "Pedidos entrantes" del operador sin recargar."""
from unittest import mock

import pytest

from pedidos.models import EstadoPedido as E, Pedido
from tests.test_hu25_cancelar_pedido import cancelar, client, confirmar, m, mover  # noqa: F401 (fixtures)

pytestmark = pytest.mark.django_db


@pytest.fixture
def avisos():
    with mock.patch("pedidos.eventos.notificar_pedido") as notificar:
        yield notificar


def test_el_cliente_cancela_un_pendiente_y_se_avisa_a_la_lista(client, m, avisos, django_capture_on_commit_callbacks):
    pedido = confirmar(client, m)
    avisos.reset_mock()  # la creación del pedido también avisa

    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(cancelar(pedido.pk)).status_code == 200

    (avisado,), _ = avisos.call_args
    assert avisado.pk == pedido.pk
    assert Pedido.objects.get(pk=pedido.pk).estado == E.CANCELADO


def test_cancelar_un_pedido_ya_aprobado_no_toca_la_lista(client, m, avisos, django_capture_on_commit_callbacks):
    pedido = confirmar(client, m)
    mover(pedido, E.RECIBIDO)
    avisos.reset_mock()

    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(cancelar(pedido.pk)).status_code == 200

    avisos.assert_not_called()

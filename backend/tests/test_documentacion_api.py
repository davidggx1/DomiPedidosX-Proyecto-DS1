"""SCRUM-120 · La documentación de cobertura, capacidad y clientes sigue siendo correcta."""
import pytest
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema


@pytest.fixture(scope="module")
def esquema():
    return SchemaGenerator().get_schema(request=None, public=True)


def operacion(esquema, ruta, metodo):
    return esquema["paths"][ruta][metodo]


def componente(esquema, ref):
    return esquema["components"]["schemas"][ref.split("/")[-1]]


def resolver(esquema, campo):
    """Sigue $ref y el allOf con que se envuelven los campos de solo lectura."""
    if "allOf" in campo:
        campo = campo["allOf"][0]
    if "$ref" in campo:
        campo = componente(esquema, campo["$ref"])
    return campo


def cuerpo(operacion_api):
    return operacion_api["requestBody"]["content"]["application/json"]["schema"]["$ref"]


def respuesta(operacion_api, codigo):
    return operacion_api["responses"][codigo]["content"]["application/json"]["schema"]


def test_el_esquema_cumple_openapi(esquema):
    validate_schema(esquema)


@pytest.mark.parametrize(
    "ruta,metodo,etiqueta",
    [
        ("/api/sedes/validar-cobertura/", "post", "Cobertura"),
        ("/api/zonas-cobertura/", "get", "Cobertura"),
        ("/api/zonas-cobertura/", "post", "Cobertura"),
        ("/api/zonas-cobertura/{id}/", "delete", "Cobertura"),
        ("/api/capacidades/", "get", "Capacidad"),
        ("/api/capacidades/", "post", "Capacidad"),
        ("/api/pedidos/capacidad/", "get", "Capacidad"),
        ("/api/usuarios/clientes/", "get", "Clientes"),
        ("/api/usuarios/clientes/{id}/", "get", "Clientes"),
    ],
)
def test_cada_endpoint_tiene_resumen_y_etiqueta(esquema, ruta, metodo, etiqueta):
    op = operacion(esquema, ruta, metodo)

    assert op.get("summary")
    assert op["tags"] == [etiqueta]


def test_las_etiquetas_tienen_descripcion(esquema):
    descritas = {tag["name"] for tag in esquema["tags"] if tag.get("description")}

    assert {"Cobertura", "Capacidad", "Clientes"} <= descritas


def test_validar_cobertura_documenta_coordenadas_y_respuesta_real(esquema):
    op = operacion(esquema, "/api/sedes/validar-cobertura/", "post")

    solicitud = componente(esquema, cuerpo(op))
    assert set(solicitud["required"]) == {"latitud", "longitud"}

    respuesta_ok = componente(esquema, respuesta(op, "200")["$ref"])
    assert {"cubierto", "mensaje", "sede", "sede_mas_cercana"} <= set(respuesta_ok["properties"])

    sede = resolver(esquema, respuesta_ok["properties"]["sede"])
    assert {"tarifa_domicilio", "pedido_minimo", "tiempo_estimado"} <= set(sede["properties"])


def test_estado_de_capacidad_documenta_sus_estados(esquema):
    op = operacion(esquema, "/api/pedidos/capacidad/", "get")

    forma = componente(esquema, respuesta(op, "200")["$ref"])
    estado = resolver(esquema, forma["properties"]["estado"])
    assert set(estado["enum"]) == {"disponible", "saturada", "sin_franja"}
    assert {"400", "403", "404"} <= set(op["responses"])


def test_eliminar_zona_en_uso_documenta_el_409(esquema):
    assert "409" in operacion(esquema, "/api/zonas-cobertura/{id}/", "delete")["responses"]


def test_el_tipo_de_zona_es_radio_o_poligono(esquema):
    tipo = resolver(esquema, componente(esquema, "ZonaCobertura")["properties"]["tipo"])

    assert set(tipo["enum"]) == {"radio", "poligono"}

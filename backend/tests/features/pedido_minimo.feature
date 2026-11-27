# language: es
# HU-57 · Pedido mínimo por zona de cobertura (criterios de aceptación con escenarios, Clase 11)
Característica: Pedido mínimo de la zona
  Como cliente
  Quiero saber si mi pedido alcanza el mínimo de mi zona
  Para no confirmar un pedido que la sede no va a despachar

  Antecedentes:
    Dado que mi dirección está en una zona con pedido mínimo de $10.000 y domicilio de $3.000

  # Camino feliz y valores límite: el borde de la regla está en $10.000 exactos
  Esquema del escenario: Pedidos que alcanzan el mínimo se confirman
    Dado que mi carrito suma <subtotal>
    Cuando confirmo el pedido
    Entonces el pedido queda registrado

    Ejemplos:
      | caso                  | subtotal |
      | exactamente el mínimo | $10.000  |
      | justo sobre el mínimo | $10.001  |
      | muy sobre el mínimo   | $25.000  |

  # Error y valores límite: un peso por debajo ya no alcanza
  Esquema del escenario: Pedidos por debajo del mínimo se rechazan e informan cuánto falta
    Dado que mi carrito suma <subtotal>
    Cuando confirmo el pedido
    Entonces el pedido no se envía
    Y veo que me faltan <faltante> para el mínimo

    Ejemplos:
      | caso                  | subtotal | faltante |
      | justo bajo el mínimo  | $9.999   | $1       |
      | la mitad del mínimo   | $5.000   | $5.000   |

  Escenario: El domicilio no cuenta para el mínimo
    Dado que mi carrito suma $8.000
    Cuando confirmo el pedido
    Entonces el pedido no se envía
    Y veo que me faltan $2.000 para el mínimo
    Pero no se crea ningún pedido

  # Alternativo: otra forma válida de llegar al mismo objetivo
  Escenario: Una zona sin pedido mínimo acepta cualquier valor
    Dado que la zona no tiene pedido mínimo
    Y que mi carrito suma $5.000
    Cuando confirmo el pedido
    Entonces el pedido queda registrado

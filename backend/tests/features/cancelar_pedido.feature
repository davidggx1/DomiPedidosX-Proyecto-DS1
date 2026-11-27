# language: es
# HU-25 · El cliente cancela su pedido antes de que entre a preparación
Característica: Cancelar mi pedido
  Como cliente
  Quiero cancelar un pedido que la cocina todavía no empezó
  Para no recibir ni pagar algo que ya no quiero

  Antecedentes:
    Dado que pedí 2 hamburguesas y quedan 3 en el inventario de la sede

  # Camino feliz: los dos estados en los que todavía se puede cancelar
  Esquema del escenario: Cancelar antes de que la cocina empiece
    Dado que mi pedido está "<estado>"
    Cuando cancelo el pedido
    Entonces el pedido queda "Cancelado"
    Y el inventario de la sede vuelve a 5 hamburguesas

    Ejemplos:
      | estado                  |
      | Pendiente de aprobación |
      | Recibido                |

  # Límite y error: "En preparación" es el primer estado en el que ya no se puede
  Esquema del escenario: No se puede cancelar cuando la cocina ya empezó
    Dado que mi pedido está "<estado>"
    Cuando cancelo el pedido
    Entonces veo que el pedido no se puede cancelar
    Y el pedido sigue "<estado>"
    Pero el inventario de la sede sigue en 3 hamburguesas

    Ejemplos:
      | estado         |
      | En preparación |
      | En camino      |

  Escenario: Cancelar un pedido que ya está cancelado
    Dado que ya cancelé mi pedido
    Cuando cancelo el pedido
    Entonces veo que el pedido no se puede cancelar
    Y el pedido sigue "Cancelado"

  Escenario: Nadie puede cancelar el pedido de otro cliente
    Dado que otro cliente intenta cancelar mi pedido
    Entonces no encuentra el pedido
    Y el pedido sigue "Pendiente de aprobación"

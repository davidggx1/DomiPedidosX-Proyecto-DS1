# language: es
# HU-03 · Iniciar sesión, con la protección contra fuerza bruta de la Clase 10
Característica: Iniciar sesión
  Como cliente registrado
  Quiero iniciar sesión con mi correo y mi contraseña
  Para acceder a mi cuenta de forma segura

  Antecedentes:
    Dado que tengo una cuenta con el correo "ana@correo.com"

  Escenario: Credenciales correctas
    Cuando inicio sesión con mi contraseña
    Entonces entro a mi cuenta

  Escenario: Contraseña incorrecta
    Cuando inicio sesión con una contraseña incorrecta
    Entonces veo el mensaje "Credenciales inválidas."
    Y no entro a mi cuenta

  # Alternativo: el correo no distingue mayúsculas
  Escenario: Correo escrito con mayúsculas
    Cuando inicio sesión como "ANA@Correo.com" con mi contraseña
    Entonces entro a mi cuenta

  Escenario: Cuenta desactivada por el administrador
    Dado que el administrador desactivó mi cuenta
    Cuando inicio sesión con mi contraseña
    Entonces veo el mensaje "La cuenta está inactiva."
    Y no entro a mi cuenta

  # Valores límite: el bloqueo empieza exactamente en el quinto fallo
  Esquema del escenario: Bloqueo después de varios intentos fallidos
    Dado que me equivoqué de contraseña <fallos> veces seguidas
    Cuando inicio sesión con mi contraseña
    Entonces <resultado>

    Ejemplos:
      | fallos | resultado                                |
      | 4      | entro a mi cuenta                        |
      | 5      | veo que hay demasiados intentos          |

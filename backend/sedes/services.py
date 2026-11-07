from datetime import datetime
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import HorarioSede, Feriado, DiaSemana

MAPA_DIAS = {
    0: DiaSemana.LUNES,
    1: DiaSemana.MARTES,
    2: DiaSemana.MIERCOLES,
    3: DiaSemana.JUEVES,
    4: DiaSemana.VIERNES,
    5: DiaSemana.SABADO,
    6: DiaSemana.DOMINGO,
}

def validar_horario_atencion_sede(sede, dt=None):
    """
    Valida si la sede puede recibir pedidos en la fecha/hora especificada.
    Lanza ValidationError (HTTP 400) si la sede está cerrada o fuera de horario.
    """
    if dt is None:
        dt = timezone.localtime()

    fecha_actual = dt.date()
    hora_actual = dt.time()

    # 1. Revisar si el día es Feriado / Festivo para la sede
    feriado = Feriado.objects.filter(sede=sede, fecha=fecha_actual).first()
    if feriado:
        if feriado.cerrado:
            raise ValidationError(
                f"La sede '{sede.nombre}' se encuentra cerrada por festivo/feriado ({feriado.descripcion})."
            )
        else:
            # Horario especial de festivo
            if not (feriado.hora_apertura <= hora_actual <= feriado.hora_cierre):
                raise ValidationError(
                    f"La sede '{sede.nombre}' está fuera de su horario especial por festivo ({feriado.hora_apertura.strftime('%H:%M')} a {feriado.hora_cierre.strftime('%H:%M')})."
                )
            return True

    # 2. Revisar horario regular según día de la semana
    dia_enum = MAPA_DIAS[dt.weekday()]
    horario = HorarioSede.objects.filter(sede=sede, dia_semana=dia_enum).first()

    if not horario:
        raise ValidationError(
            f"La sede '{sede.nombre}' no atiende los días {dia_enum.label}."
        )

    if not (horario.hora_apertura <= hora_actual <= horario.hora_cierre):
        raise ValidationError(
            f"La sede '{sede.nombre}' está fuera de su horario de atención ({horario.hora_apertura.strftime('%H:%M')} a {horario.hora_cierre.strftime('%H:%M')})."
        )

    return True
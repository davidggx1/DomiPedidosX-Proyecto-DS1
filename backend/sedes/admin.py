from django.contrib import admin

from .models import Ciudad, Sede, HorarioSede, Feriado, ZonaCobertura, CapacidadSede

admin.site.register(Ciudad)
admin.site.register(Sede)
admin.site.register(HorarioSede)
admin.site.register(Feriado)
admin.site.register(ZonaCobertura)
admin.site.register(CapacidadSede)

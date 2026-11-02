from django.contrib import admin
from .models import Ciudad, Sede, HorarioSede, Feriado, ZonaCobertura, CapacidadSede


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'ciudad', 'telefono', 'correo', 'activa', 'fecha_registro')
    list_filter = ('activa', 'ciudad')
    search_fields = ('nombre', 'direccion', 'telefono', 'barrio')


admin.site.register(Ciudad)
admin.site.register(HorarioSede)
admin.site.register(Feriado)
admin.site.register(ZonaCobertura)
admin.site.register(CapacidadSede)
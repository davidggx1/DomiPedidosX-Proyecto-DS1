from django.contrib import admin

from .models import InventarioProducto, InventarioInsumo

admin.site.register(InventarioProducto)
admin.site.register(InventarioInsumo)

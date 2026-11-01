from django.contrib import admin

from .models import CategoriaMenu, Producto, ProductoTamano, Insumo, Adicion, ProductoAdicion, ProductoInsumo

admin.site.register(CategoriaMenu)
admin.site.register(Producto)
admin.site.register(ProductoTamano)
admin.site.register(Insumo)
admin.site.register(Adicion)
admin.site.register(ProductoAdicion)
admin.site.register(ProductoInsumo)

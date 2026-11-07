from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Cliente, DireccionEntrega, Empleado, Repartidor, Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("email", "username")


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    list_display = ("email", "username", "is_active", "is_staff")
    search_fields = ("email", "username")
    ordering = ("email",)
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2")}),
    )


admin.site.register(Cliente)
admin.site.register(Empleado)
admin.site.register(Repartidor)
admin.site.register(DireccionEntrega)

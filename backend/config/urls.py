"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from usuarios.views import LoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Mismo login que /api/usuarios/login/, con su límite de intentos: si fuera el
    # TokenObtainPairView sin cambios, sería una puerta trasera para la fuerza bruta.
    path("api/auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("sedes.urls")),  # 2. Rutas de la app sedes
    path("api/usuarios/", include("usuarios.urls")),
    path("api/menu/", include("menu.urls")),
    path("api/inventario/", include("inventario.urls")),
    path("api/pedidos/", include("pedidos.urls")),
    path("api/", include("promociones.urls")),
]

# In development, Django serves the uploaded images from /media/
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

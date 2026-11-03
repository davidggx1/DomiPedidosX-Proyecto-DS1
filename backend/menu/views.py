from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Producto
from .serializers import ProductoImagenSerializer


class ProductoImagenView(generics.GenericAPIView):
    """Uploads, replaces or deletes the product image (admin only)"""

    queryset = Producto.objects.all()
    serializer_class = ProductoImagenSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        producto = self.get_object()
        imagen_anterior = producto.imagen.name

        serializer = self.get_serializer(producto, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # When replacing the image, the old file is deleted from storage
        if imagen_anterior and imagen_anterior != producto.imagen.name:
            producto.imagen.storage.delete(imagen_anterior)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        producto = self.get_object()
        if producto.imagen:
            producto.imagen.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

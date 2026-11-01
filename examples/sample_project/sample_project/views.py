from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import CharField, Serializer
from rest_framework.views import APIView


class HelloSerializer(Serializer):
    message = CharField()


class HelloView(APIView):
    """Simple endpoint so the sample schema has something to diff."""

    @extend_schema(responses=HelloSerializer)
    def get(self, request):
        return Response({"message": "hello from swagger-diff-ui sample"})

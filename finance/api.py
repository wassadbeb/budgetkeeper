"""Представления REST API (DRF): CRUD операций и служебные эндпоинты."""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import Account, Category, Operation
from .serializers import OperationSerializer


class OperationListCreateView(APIView):
    """GET — список операций; POST — создание операции."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        operations = Operation.objects.filter(user=request.user, is_deleted=False)
        serializer = OperationSerializer(operations, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OperationSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class OperationDetailView(APIView):
    """GET/PUT/DELETE — работа с конкретной операцией пользователя."""

    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(
            Operation, pk=pk, user=request.user, is_deleted=False
        )

    def get(self, request, pk):
        operation = self.get_object(request, pk)
        serializer = OperationSerializer(operation, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        operation = self.get_object(request, pk)
        serializer = OperationSerializer(
            operation, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    def delete(self, request, pk):
        operation = self.get_object(request, pk)
        operation.is_deleted = True
        operation.save(update_fields=["is_deleted"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class StatsAPIView(APIView):
    """Статистика системы — только для администратора (демонстрация 403)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response(
                {"error": "Forbidden", "message": "Требуются права администратора."},
                status=status.HTTP_403_FORBIDDEN,
            )
        total_operations = Operation.objects.count()
        return Response(
            {
                "total_users": User.objects.count(),
                "total_operations": total_operations,
                "total_accounts": Account.objects.count(),
                "total_categories": Category.objects.count(),
            },
            status=status.HTTP_200_OK,
        )

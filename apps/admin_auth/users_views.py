from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter

from django.contrib.auth import get_user_model

from users.models.clients import Client
from users.models.partners import Partner
from users.serializers import ClientProfileSerializer, PartnerProfileSerializer
from apps.admin_auth.permissions import IsAdminUser
from apps.admin_auth.authentication import AdminJWTAuthentication

User = get_user_model()


class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminClientsListView(generics.ListAPIView):
    """List all clients - admin only"""
    queryset = Client.objects.all().order_by('-created_at')
    serializer_class = ClientProfileSerializer
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = AdminUserPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['created_at', 'first_name', 'email']


class AdminPartnersListView(generics.ListAPIView):
    """List all partners - admin only"""
    queryset = Partner.objects.all().order_by('-created_at')
    serializer_class = PartnerProfileSerializer
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = AdminUserPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name', 'phone_number', 'username']
    ordering_fields = ['created_at', 'first_name', 'email']

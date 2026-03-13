from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from django.db.models import Q
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.admin_auth.authentication import AdminJWTAuthentication
from users.authentication import PartnerJWTAuthentication
from users.models.partners import Partner
from notification.service import NotificationService
from .models import Conversation, ChatMessage
from .serializers import ChatMessageSerializer, ConversationSerializer, ActorSerializer

User = get_user_model()


class IsAuthenticatedActor(BasePermission):
    """Accept authenticated admin or partner actor."""

    def has_permission(self, request, view):
        return request.user is not None and request.auth is not None


def is_admin_actor(user) -> bool:
    return isinstance(user, User)


def is_partner_actor(user) -> bool:
    return isinstance(user, Partner)


class ChatViewSet(viewsets.GenericViewSet):
    authentication_classes = [AdminJWTAuthentication, PartnerJWTAuthentication]
    permission_classes = [IsAuthenticatedActor]
    serializer_class = ChatMessageSerializer

    @staticmethod
    def _room_name(actor_type: str, actor_id: int) -> str:
        return f"chat_{actor_type}_{actor_id}"

    @staticmethod
    def _push_ws_event(actor_type: str, actor_id: int, event_type: str, payload: dict):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        async_to_sync(channel_layer.group_send)(
            ChatViewSet._room_name(actor_type, actor_id),
            {
                "type": event_type,
                "message": payload,
            },
        )

    @action(detail=False, methods=['get'])
    def conversations(self, request):
        """Get all conversations for the current actor."""
        user = request.user

        if is_admin_actor(user):
            queryset = Conversation.objects.filter(admin_user=user).select_related('partner').order_by('-updated_at')
        elif is_partner_actor(user):
            queryset = Conversation.objects.filter(partner=user).select_related('admin_user').order_by('-updated_at')
        else:
            return Response([], status=status.HTTP_200_OK)

        conversations = []
        for conversation in queryset:
            last_message = conversation.messages.order_by('-created_at').first()

            if is_admin_actor(user):
                unread_count = conversation.messages.filter(
                    receiver_admin=user,
                    sender_partner__isnull=False,
                    is_read=False,
                ).count()
                counterpart = ActorSerializer.from_partner(conversation.partner)
            else:
                unread_count = conversation.messages.filter(
                    receiver_partner=user,
                    sender_admin__isnull=False,
                    is_read=False,
                ).count()
                counterpart = ActorSerializer.from_admin(conversation.admin_user)

            conversations.append({
                'counterpart': counterpart,
                'conversation_id': conversation.id,
                'last_message': last_message,
                'unread_count': unread_count,
            })

        serializer = ConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='messages/(?P<partner_id>[^/.]+)')
    def messages(self, request, partner_id=None):
        """Get all messages with a specific counterpart."""
        user = request.user

        conversation = None
        if is_admin_actor(user):
            partner = Partner.objects.filter(id=partner_id).first()
            if not partner:
                return Response({'error': 'Partner not found'}, status=status.HTTP_404_NOT_FOUND)
            conversation, _ = Conversation.objects.get_or_create(admin_user=user, partner=partner)
        elif is_partner_actor(user):
            admin_user = User.objects.filter(id=partner_id, is_active=True).first()
            if not admin_user:
                return Response({'error': 'Admin user not found'}, status=status.HTTP_404_NOT_FOUND)
            conversation, _ = Conversation.objects.get_or_create(admin_user=admin_user, partner=user)
        else:
            return Response({'error': 'Unauthorized actor'}, status=status.HTTP_403_FORBIDDEN)

        messages = conversation.messages.order_by('created_at')

        if is_admin_actor(user):
            conversation.messages.filter(receiver_admin=user, is_read=False).update(is_read=True)
        else:
            conversation.messages.filter(receiver_partner=user, is_read=False).update(is_read=True)

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a message to counterpart actor."""
        receiver_id = request.data.get('receiver_id')
        content = request.data.get('content', '').strip()

        if not receiver_id or not content:
            return Response(
                {'error': 'receiver_id and content are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        sender = request.user
        if is_admin_actor(sender):
            partner = Partner.objects.filter(id=receiver_id).first()
            if not partner:
                return Response({'error': 'Partner not found'}, status=status.HTTP_404_NOT_FOUND)
            conversation, _ = Conversation.objects.get_or_create(admin_user=sender, partner=partner)
            message = ChatMessage.objects.create(
                conversation=conversation,
                sender_admin=sender,
                receiver_partner=partner,
                content=content,
            )
        elif is_partner_actor(sender):
            admin_user = User.objects.filter(id=receiver_id, is_active=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_active=True, is_staff=True).order_by('id').first()
            if not admin_user:
                return Response({'error': 'No admin user available'}, status=status.HTTP_400_BAD_REQUEST)

            conversation, _ = Conversation.objects.get_or_create(admin_user=admin_user, partner=sender)
            message = ChatMessage.objects.create(
                conversation=conversation,
                sender_partner=sender,
                receiver_admin=admin_user,
                content=content,
            )
        else:
            return Response({'error': 'Unauthorized actor'}, status=status.HTTP_403_FORBIDDEN)

        conversation.save(update_fields=['updated_at'])
        serializer = ChatMessageSerializer(message)
        data = serializer.data

        if is_admin_actor(sender):
            sender_name = getattr(sender, "get_full_name", lambda: "")() or getattr(sender, "username", "") or "Admin"
            message_preview = content if len(content) <= 120 else f"{content[:117]}..."
            NotificationService.send_to_partner(
                partner=partner,
                title=sender_name,
                message=message_preview,
                notification_type="message",
                data={
                    "type": "chat_message",
                    "conversation_id": conversation.id,
                    "message_id": message.id,
                    "sender_id": sender.id,
                    "sender_type": "admin",
                    "receiver_id": partner.id,
                    "receiver_type": "partner",
                    "message_preview": message_preview,
                    "sender_name": sender_name,
                },
            )

        # Push to receiver and sender sockets to keep both clients in sync when REST endpoint is used.
        receiver_type = data.get('receiver_type')
        receiver_id = data.get('receiver_id')
        sender_type = data.get('sender_type')
        sender_id = data.get('sender_id')

        if receiver_type and receiver_id:
            self._push_ws_event(receiver_type, int(receiver_id), 'chat_message', data)
        if sender_type and sender_id:
            self._push_ws_event(sender_type, int(sender_id), 'chat_message', data)

        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='read')
    def read_messages(self, request):
        message_ids = request.data.get('message_ids') or []
        if not isinstance(message_ids, list):
            return Response({'error': 'message_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        queryset = ChatMessage.objects.filter(id__in=message_ids)
        if is_admin_actor(user):
            queryset = queryset.filter(receiver_admin=user)
        elif is_partner_actor(user):
            queryset = queryset.filter(receiver_partner=user)
        else:
            return Response({'error': 'Unauthorized actor'}, status=status.HTTP_403_FORBIDDEN)

        queryset.update(is_read=True)

        partner_id = request.data.get('partner_id')
        partner_type = request.data.get('partner_type')
        if partner_id and partner_type:
            self._push_ws_event(
                str(partner_type),
                int(partner_id),
                'messages_read',
                {
                    'partner_id': getattr(user, 'id', None),
                    'partner_type': 'admin' if is_admin_actor(user) else 'partner',
                    'message_ids': message_ids,
                },
            )

        return Response({'updated': len(message_ids)}, status=status.HTTP_200_OK)

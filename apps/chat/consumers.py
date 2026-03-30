import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from users.models.partners import Partner
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from users.tokens import TokenMetadata
from .serializers import ChatMessageSerializer
from .services import ChatRoutingError, get_or_create_conversation_for_message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_params = parse_qs(self.scope['query_string'].decode())
        token = (query_params.get('token') or [None])[0]

        if not token:
            await self.close()
            return

        actor = await self.get_actor_from_token(token)
        if not actor:
            await self.close()
            return

        self.actor_type = actor['actor_type']
        self.actor_id = actor['actor_id']
        self.room_group_name = self._room_name(self.actor_type, self.actor_id)

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data or '{}')
        message_type = data.get('type')

        if message_type == 'message':
            await self.handle_message(data.get('data', {}))
        elif message_type == 'read':
            await self.handle_read(data.get('data', {}))
        elif message_type == 'typing':
            await self.handle_typing(data.get('data', {}))
        elif message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'data': {}
            }))

    async def handle_message(self, data):
        receiver_id = data.get('receiver_id')
        receiver_type = data.get('receiver_type')
        content = data.get('content', '').strip()

        if not receiver_id or not receiver_type or not content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'receiver_id, receiver_type and content are required',
            }))
            return

        message = await self.save_message(
            sender_type=self.actor_type,
            sender_id=self.actor_id,
            receiver_id=receiver_id,
            receiver_type=receiver_type,
            content=content
        )

        if not message:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Unable to deliver message',
            }))
            return

        await self.channel_layer.group_send(
            self._room_name(message['receiver_type'], message['receiver_id']),
            {
                'type': 'chat_message',
                'message': message
            }
        )

        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': message
        }))

    async def handle_read(self, data):
        partner_id = data.get('partnerId')
        partner_type = data.get('partnerType')
        message_ids = data.get('messageIds') or []

        if message_ids:
            await self.mark_messages_as_read(message_ids)

            if partner_id and partner_type:
                await self.channel_layer.group_send(
                    self._room_name(partner_type, partner_id),
                    {
                        'type': 'messages_read',
                        'partner_id': self.actor_id,
                        'partner_type': self.actor_type,
                        'message_ids': message_ids
                    }
                )

    async def handle_typing(self, data):
        partner_id = data.get('partnerId')
        partner_type = data.get('partnerType')
        is_typing = data.get('isTyping', False)

        if partner_id and partner_type:
            await self.channel_layer.group_send(
                self._room_name(partner_type, partner_id),
                {
                    'type': 'user_typing',
                    'user_id': self.actor_id,
                    'user_type': self.actor_type,
                    'is_typing': is_typing
                }
            )

    # Channel layer message handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message']
        }))
    
    async def messages_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'data': {
                'partnerId': event['partner_id'],
                'partnerType': event['partner_type'],
                'messageIds': event['message_ids']
            }
        }))
    
    async def user_typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'data': {
                'userId': event['user_id'],
                'userType': event['user_type'],
                'isTyping': event['is_typing']
            }
        }))

    # Database operations
    @staticmethod
    def _room_name(actor_type, actor_id):
        return f'chat_{actor_type}_{actor_id}'

    @database_sync_to_async
    def get_actor_from_token(self, token):
        try:
            access_token = AccessToken(token)
            actor_type = access_token.get(TokenMetadata.TOKEN_USER_TYPE)
            subject = access_token.get(TokenMetadata.TOKEN_SUBJECT)

            if actor_type == 'admin':
                user = User.objects.filter(id=subject, is_active=True).first()
                if not user:
                    return None
                return {'actor_type': 'admin', 'actor_id': user.id}

            if actor_type == 'partner':
                partner = Partner.objects.filter(guid=subject, is_active=True).first()
                if not partner:
                    return None
                return {'actor_type': 'partner', 'actor_id': partner.id}

            return None
        except (TokenError, ValueError):
            return None

    @database_sync_to_async
    def save_message(self, sender_type, sender_id, receiver_id, receiver_type, content):
        try:
            from .models import ChatMessage
            from notification.service import NotificationService

            try:
                conversation, admin, partner = get_or_create_conversation_for_message(
                    sender_type=sender_type,
                    sender_id=int(sender_id),
                    receiver_id=int(receiver_id),
                    receiver_type=str(receiver_type),
                )
            except ChatRoutingError:
                return None

            if sender_type == 'admin':
                message = ChatMessage.objects.create(
                    conversation=conversation,
                    sender_admin=admin,
                    receiver_partner=partner,
                    content=content,
                )

                sender_name = (
                    (getattr(admin, 'get_full_name', lambda: '')() or '').strip()
                    or getattr(admin, 'username', '')
                    or 'Admin'
                )
                message_preview = content if len(content) <= 120 else f"{content[:117]}..."
                try:
                    NotificationService.send_to_partner(
                        partner=partner,
                        title=sender_name,
                        message=message_preview,
                        data={
                            'type': 'chat_message',
                            'conversation_id': conversation.id,
                            'message_id': message.id,
                            'sender_id': admin.id,
                            'sender_type': 'admin',
                            'receiver_id': partner.id,
                            'receiver_type': 'partner',
                            'message_preview': message_preview,
                            'sender_name': sender_name,
                        },
                    )
                except Exception as push_error:
                    print(f"Error sending partner push notification: {push_error}")
            else:
                message = ChatMessage.objects.create(
                    conversation=conversation,
                    sender_partner=partner,
                    receiver_admin=admin,
                    content=content,
                )

            conversation.save(update_fields=['updated_at'])
            payload = ChatMessageSerializer(message).data
            payload['receiver_type'] = 'partner' if message.receiver_partner_id else 'admin'
            payload['sender_type'] = 'admin' if message.sender_admin_id else 'partner'
            return payload
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def mark_messages_as_read(self, message_ids):
        try:
            from .models import ChatMessage

            queryset = ChatMessage.objects.filter(id__in=message_ids)
            if self.actor_type == 'admin':
                queryset = queryset.filter(receiver_admin_id=self.actor_id)
            else:
                queryset = queryset.filter(receiver_partner_id=self.actor_id)

            queryset.update(is_read=True)
        except Exception as e:
            print(f"Error marking messages as read: {e}")

"""
WebSocket consumers for real-time updates.

This module handles WebSocket connections for broadcasting real-time updates
when presets or queue entries are created, modified, or deleted.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class QueueUpdatesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for broadcasting queue and preset updates.

    Users connect to this consumer to receive real-time notifications when:
    - Presets are created, edited, or deleted
    - Queue entries are submitted, cancelled, or reordered
    - Machine status changes
    """

    async def connect(self):
        """
        Called when a WebSocket connection is initiated.
        Adds the user to the 'queue_updates' group and user-specific notification group.
        """
        # Join the queue updates group
        self.room_group_name = 'queue_updates'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Join user-specific notification group if authenticated
        self.user_notification_group = None
        if self.scope["user"].is_authenticated:
            self.user_notification_group = f'user_{self.scope["user"].id}_notifications'
            await self.channel_layer.group_add(
                self.user_notification_group,
                self.channel_name
            )

        await self.accept()

    async def disconnect(self, close_code):
        """
        Called when a WebSocket connection is closed.
        Removes the user from the 'queue_updates' group and user-specific notification group.
        """
        # Leave the queue updates group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Leave user-specific notification group
        if self.user_notification_group:
            await self.channel_layer.group_discard(
                self.user_notification_group,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Called when a message is received from the WebSocket.
        Currently not used - all updates are server-initiated.
        """
        pass

    async def preset_update(self, event):
        """
        Handler for preset update events.
        Sends preset update notification to the WebSocket.

        Event data should include:
        - type: 'created', 'edited', 'deleted'
        - preset_id: ID of the affected preset
        - preset_data: Updated preset information (for created/edited)
        """
        await self.send(text_data=json.dumps({
            'message_type': 'preset_update',
            'update_type': event['update_type'],
            'preset_id': event.get('preset_id'),
            'preset_data': event.get('preset_data'),
        }))

    async def queue_update(self, event):
        """
        Handler for queue update events.
        Sends queue update notification to the WebSocket.

        Event data should include:
        - type: 'submitted', 'cancelled', 'moved', 'completed'
        - entry_id: ID of the affected queue entry
        - user_id: ID of the user affected (optional)
        - machine_id: ID of the affected machine (optional)
        - machine_name: Name of the affected machine (optional)
        - triggering_user_id: ID of the user who triggered the update (optional)
        """
        await self.send(text_data=json.dumps({
            'message_type': 'queue_update',
            'update_type': event['update_type'],
            'entry_id': event.get('entry_id'),
            'user_id': event.get('user_id'),
            'machine_id': event.get('machine_id'),
            'machine_name': event.get('machine_name'),
            'triggering_user_id': event.get('triggering_user_id'),
        }))

    async def notification(self, event):
        """
        Handler for user-specific notification events.
        Sends notification to the WebSocket.

        Event data should include:
        - notification_id: ID of the notification
        - notification_type: Type of notification
        - title: Notification title
        - message: Notification message
        - created_at: Timestamp
        """
        await self.send(text_data=json.dumps({
            'message_type': 'notification',
            'notification_id': event.get('notification_id'),
            'notification_type': event.get('notification_type'),
            'title': event.get('title'),
            'message': event.get('message'),
            'created_at': event.get('created_at'),
        }))

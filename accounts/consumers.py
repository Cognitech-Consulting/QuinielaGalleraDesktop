import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TicketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Handle WebSocket disconnection
        pass

    async def receive(self, text_data):
        # Handle messages received from WebSocket
        data = json.loads(text_data)
        message = data.get('message', 'No message sent')
        # Echo the message back
        await self.send(text_data=json.dumps({'message': f"Received: {message}"}))

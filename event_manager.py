# event_manager.py
import discord

class EventManager:
    def __init__(self, client, ticket_handler):
        self.client = client
        self.ticket_handler = ticket_handler
        
    async def on_channel_create(self, channel):
        await self.ticket_handler.handle_ticket(channel)

    async def system_ready(self):
        print("Event Manager Ready")
        try:
            await self.ticket_handler.on_ready()
        except:
            pass

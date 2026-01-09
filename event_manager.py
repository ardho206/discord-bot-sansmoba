# event_manager.py
import discord

class EventManager:
    def __init__(self, client, ticket_handler, helper_system):
        self.client = client
        self.ticket_handler = ticket_handler
        self.helper_system = helper_system
        
    async def on_channel_create(self, thread):
        await self.ticket_handler.handle_ticket(thread)

    async def on_message(self, message):
        if message.author.bot:
            return

        await self.ticket_handler.handle_ticket_message(message)

        await self.helper_system.handle_helper_message(message)
            
    async def system_ready(self):
        print("Event Manager Ready")
        try:
            await self.ticket_handler.on_ready()
        except:
            pass
        try:
            await self.helper_system.on_ready()
        except:
            pass

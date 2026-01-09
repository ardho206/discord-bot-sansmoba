import asyncio
import discord
from messages import ticket_message, closed_ticket
from discord.ui import Button, View

class TicketHandler:
    def __init__(self, client, log_channel_id, parent_category="【🎫】・create-ticket"):
        self.client = client
        self.log_channel_id = log_channel_id
        self.parent_category = parent_category

    async def on_ready(self):
        print("Ticket Handler ready")
        
    async def handle_ticket(self, channel: discord.TextChannel):
        print(type(channel), channel.name)
        if not isinstance(channel, discord.TextChannel):
            return
        
        if not channel.category or channel.category.name != self.parent_category:
            return

        if not channel.name.startswith("ticket-"):
            return

        await asyncio.sleep(1)

        text, embed = ticket_message()
        await channel.send(content=text, embed=embed)
        
import asyncio
import discord
from messages import ticket_message, closed_ticket
from discord.ui import Button, View

SUPPORT_ROLE_ID = 1431927807579000894


class TicketHandler:
    def __init__(self, client, log_channel_id, parent_category="⌯⌲ 𝐓𝐢𝐜𝐤𝐞𝐭"):
        self.client = client
        self.log_channel_id = log_channel_id
        self.parent_category = parent_category

    async def on_ready(self):
        print("Ticket Handler ready")
        
    async def handle_ticket(self, channel: discord.TextChannel):
        if not isinstance(channel, discord.TextChannel):
            return
        
        if not channel.category or channel.category.name != self.parent_category:
            return

        if not channel.name.startswith("ticket-"):
            return

        await asyncio.sleep(2)

        try:
            async for msg in channel.history(limit=10):
                if msg.author == self.client.user:
                    return
                
            first_msg = None
            async for msg in channel.history(limit=5, oldest_first=True):
                if msg.author.bot:
                    first_msg = msg
                    break
                
            if not first_msg:
                return
            
            content = (first_msg.content or "").lower()
            
            if "💰 Purchase!" in content or "💰 purchase!" in content:
                role = channel.guild.get_role(SUPPORT_ROLE_ID)
                mention = role.mention if role else ""
                
                text, embed = ticket_message()
                await channel.send(content=f"{mention}\n{text}", embed=embed)
                
        except Exception as e:
            print("Error handling ticket:", e)
        
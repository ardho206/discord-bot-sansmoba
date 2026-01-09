import asyncio
import discord
from messages import ticket_message, closed_ticket
from discord.ui import Button, View

SUPPORT_ROLE_ID = 1431927807579000894


class TicketHandler:
    def __init__(self, client, log_channel_id, parent_category="⌯⌲ Ticket"):
        self.client = client
        self.log_channel_id = log_channel_id
        self.parent_category = parent_category

    async def on_ready(self):
        print("Ticket Handler ready")
        
    async def handle_ticket(self, channel: discord.TextChannel):
        if not channel.name.startswith("ticket-"):
            return
        
        if not channel.category or channel.category.name != self.parent_category:
            return


        await asyncio.sleep(2)

        async for msg in channel.history(limit=5, oldest_first=True):
            if msg.author.bot and msg.embeds:
                embed = msg.embeds[0]
                
                if "Purchase" in embed.description or "purchase" in embed.description.lower():
                    text, embed_reply = ticket_message()
                    await channel.send(content=text, embed=embed_reply)
                    
                    role = discord.utils.get(channel.guild.roles, id=SUPPORT_ROLE_ID)
                    if role:
                        await channel.send(f"{role.mention}")
                    return
                    
            
        
import asyncio
import discord
from messages import ticket_message, closed_ticket
from discord.ui import Button, View

class TicketHandler:
    def __init__(self, client, log_channel_id, parent_channel="【🎫】・ticket"):
        self.client = client
        self.log_channel_id = log_channel_id
        self.parent_name = parent_channel

    async def on_ready(self):
        print("Ticket Handler ready")
        
    async def handle_thread(self, thread):
        parent = thread.parent
        if not parent or parent.name != self.parent_name:
            return

        if not thread.name.startswith("ticket-"):
            return

        await thread.join()
        await asyncio.sleep(2)

        text, embed = ticket_message()
        await thread.send(content=text, embed=embed)
        
    async def handle_ticket_message(self, message):
        channel = message.channel

        if not isinstance(channel, discord.Thread):
            return

        if not channel.name.startswith("ticket-"):
            return

        content = message.content.lower()

        if content == ".done":
            await self.close_ticket(channel, message.author, "done transaksi pembelian script")

        elif content == ".close":
            await self.close_ticket(channel, message.author, "close no respon pembeli")

    async def close_ticket(self, thread, staff_user, reason):
        log_channel = self.client.get_channel(self.log_channel_id)

        opener_name = thread.name.replace("ticket-", "")
        guild = thread.guild
        opener_member = discord.utils.get(guild.members, name=opener_name)

        embed = discord.Embed(
            title="SansMoba Ticket Transcript",
            color=0xA64DFF,
            description=(
                f"**Ticket Info**\n"
            )
        )

        embed.add_field(name="<:approved:1448228219185791047> **Opened By:**", value=f"<:reply:1448239575305551922>{opener_member.mention}", inline=True)
        embed.add_field(name="<:denied:1448205814371319884> **Closed By:**", value=f"<:reply:1448239575305551922>{staff_user.mention}", inline=True)
        
        embed.add_field(name="", value=f"Ticket ID: `{thread.name}`", inline=False)
        embed.add_field(name="", value=f"Reason: **{reason}**", inline=False)
        embed.set_footer(text="<:sansmoba:1448653387867361352> SansMoba Premium — Ticket System")

        view = View()
        view.add_item(Button(label="Lihat Ticket", url=thread.jump_url, emoji="<:done:1448597504219287552>"))

        await log_channel.send(embed=embed, view=view)

        await thread.send(content=closed_ticket())
        await asyncio.sleep(2)
        await thread.edit(archived=True, locked=True)
import discord

def make_embed(title, desc, color=0xA64DFF):
    return discord.Embed(title=title, description=desc, color=color)

def error_embed(msg):
    return make_embed("Error", f"⚠️ {msg}", color=0xFF0000)

def success_embed(msg):
    return make_embed("Sukses", f"✅ {msg}", color=0x00FF00)

def main_embed():
    embed = discord.Embed(
        color=0xA64DFF,
        title="🌟 SansMoba Premium Panel",
        description=(
            "- Klik **Redeem Key** untuk redeem key premium\n"
            "- Klik **Get Script** untuk mendapatkan script\n"
            "- Klik **Manage Account** untuk reset username\n"
            "- Klik **Reset Key** untuk reset key\n"
        )
    )

    embed.add_field(
        name="**🌐 TUTORIAL REDEEM KEY**",
        value=(
            "> 1. Klik tombol **REDEEM KEY**\n"
            "> 2. Masukkan username roblox dan key premium\n"
            "> 3. Klik submit dan tunggu hingga muncul pesan sukses\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**🔴 NOTES**",
        value=(
            "- Jika terpental dari premium, periksa username yang dimasukkan dan **pastikan username/key benar**\n"
            "- **Reset key hanya untuk premium yang ingin menambah slot akun**, jika ingin reset key silahkan open ticket\n"
            "https://discord.com/channels/1360567703709941782/1376065309949169774"
        ),
        inline=False
    )

    embed.set_image(url="https://media.discordapp.net/attachments/1436332127779164190/1447550851622371338/IMG-20251111-WA0003.jpg")
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/1436332127779164190/1447582512917512352/logo.webp")

    embed.set_footer(
        text="Pastikan username roblox benar (format: username) tanpa @"
    )

    return embed

ticket_text = (
    "## **🛒 Pricelist SansMoba Premium:**\n"
    "> 1 SLOT KEY = IDR 35.000\n"
    "> 2 SLOT KEY = IDR 50.000\n"
    "> 5 SLOT KEY = IDR 100.000\n"
    "> 10 SLOT KEY = IDR 150.000\n"
    "> 15 SLOT KEY = IDR 200.000\n\n"
    
    "**Indonesian:**\n"
    "__**Note**__: Slot key adalah batas penggunaan memakai script secara bersamaan, jika anda membeli lebih dari 1 slot key maka bisa untuk menjalankan script oleh banyak penggunaan sekaligus\n"
    "**1 slot key sudah bisa berganti akun dan berganti device secara bebas tanpa ada batasan limit dan permanen!**\n\n"
    
    "**English:**\n"
    "__**Note**__: Slot key is the limit of using script together, if you buy more than 1 slot key, you can run script by many users at the same time\n"
    "**1 slot key can change account and device freely without any limit and permanent!**\n\n"
    
    "** 💳 Metode Pembayaran:**"
)

def ticket_message():
    embed = discord.Embed(
        description= (
            "REK BCA : `6970359981` A/N Alxx Sulxxx\n"
            "DANA : `087777338122` A/N Alxx Sulxxx\n"
            "SHOPEEPAY : `087777338122` A/N Alxx Sulxxx\n"
            "GOPAY : `087777338122` A/N Alxx Sulxxx\n"
            "**Click/Tap To Copy No Payment**\n\n"
        )
    )

    embed.set_image(url="https://media.discordapp.net/attachments/1435693286315790477/1435740913820242141/IMG-20251105-WA00351.jpg")
    
    return ticket_text, embed

def get_script():
    script_text = (
        "### **For Mobile Users:**\n"
        "`loadstring(game:HttpGet('https://raw.githubusercontent.com/DyyITT/SansMobaHub/refs/heads/main/FishIt-Premium'))()`\n\n"
        "### **For PC Users:**\n"
        "```loadstring(game:HttpGet('https://raw.githubusercontent.com/DyyITT/SansMobaHub/refs/heads/main/FishIt-Premium'))()```\n\n"
    )
    
    return script_text

def closed_ticket():
    ticket_text = (
        "## **Terimakasih Sudah Menggunakan Layanan Kami :heart:**\n"
        "**Support** : https://discord.com/channels/1360567703709941782/1376077073478848523\n"
        "**Rating**  : https://discord.com/channels/1360567703709941782/1438917050251874356\n\n"
        "**SansMoba Official**"
    )
    
    return ticket_text
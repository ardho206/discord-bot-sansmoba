import os
import sys
import base64
import json
import random
import string
import asyncio
import datetime
import time
import sqlite3
from urllib.parse import quote
import discord
from discord.ui import Button, View, Modal, TextInput
from discord import app_commands
import aiohttp
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")
REPO_2 = os.getenv("GITHUB_REPO_2")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
FILE_PATH = os.getenv("FILE_PATH")
FILE_PATH_2 = os.getenv("FILE_PATH_2")
BRANCH = os.getenv("BRANCH", "main")
GUILD_ID = 1360567703709941782
ALLOWED_USERS = [1154602289097617450, 938692894410297414]

# ---------- DB load ----------
DB_PATH = "/data/data.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    key TEXT PRIMARY KEY,
    slots INTEGER,
    used TEXT,
    created_at REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    key TEXT,
    usernames TEXT
)
""")

conn.commit()

db_lock = asyncio.Lock()

# ---------- Embed builder ----------
API_BASE = "https://api.github.com"
def make_embed(title, desc, color=0xA64DFF):
    return discord.Embed(title=title, description=desc, color=color)

def error_embed(msg):
    return make_embed("Error", f"⚠️ {msg}", color=0xFF0000)

def success_embed(msg):
    return make_embed("Sukses", f"✅ {msg}", color=0x00FF00)

# --- Github ---
async def fetch_file(session, repo, path, branch):
    path_enc = quote(path)
    url = f"{API_BASE}/repos/{repo}/contents/{path_enc}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {"ref": branch}
    async with session.get(url, headers=headers, params=params) as r:
        if r.status != 200:
            return None, r.status, await r.text()
        return await r.json(), r.status, None
async def update_file(session, repo, path, branch, new_content, sha, message):
    path_enc = quote(path)
    url = f"{API_BASE}/repos/{repo}/contents/{path_enc}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "message": message,
        "content": base64.b64encode(new_content.encode()).decode(),
        "branch": branch,
        "sha": sha
    }
    async with session.put(url, headers=headers, data=json.dumps(payload)) as r:
        return r.status, await r.text()

# ---------- Modal ----------
class UsernameModal(Modal):
    def __init__(self, key_slot=None):
        super().__init__(title="Masukkan Username + Key")
        self.key_slot = key_slot
        self.username_input = TextInput(label="Username Roblox", placeholder="Masukkan Username...")
        self.key_input = TextInput(label="Key", placeholder="Masukkan Key...") if key_slot is None else None
        self.add_item(self.username_input)
        if self.key_input:
            self.add_item(self.key_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # <--- ini bikin interaction hidup
        username = self.username_input.value.strip()
        key = self.key_input.value.strip() if self.key_input else self.key_slot
        uid = str(interaction.user.id)

        if not username or not key:
            await interaction.followup.send(embed=error_embed("Username atau Key kosong!"), ephemeral=True)
            return

        # ambil data key dari DB
        async with db_lock:
            cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
            key_data = cursor.fetchone()
        if not key_data:
            await interaction.followup.send(embed=error_embed("Key tidak valid!"), ephemeral=True)
            return

        total_slots, used_json = key_data
        used_list = json.loads(used_json) if key_data[1] else []

        if len(used_list) >= total_slots:
            await interaction.followup.send(embed=error_embed("Slot key habis!"), ephemeral=True)
            return

        # lock github biar ga bentrok
        async with asyncio.Lock():
            async with aiohttp.ClientSession() as session:
                # repo 1: hapus klo ada
                file_data1, status1, err1 = await fetch_file(session, REPO, FILE_PATH, BRANCH)
                if file_data1 is None:
                    await interaction.followup.send(embed=error_embed("Jika anda melihat pesan ini, hubungi admin!"), ephemeral=True)
                    return
                sha1 = file_data1.get("sha")
                old_content1 = base64.b64decode(file_data1.get("content", "").encode()).decode() if file_data1.get("content") else ""
                lines1 = [l.strip() for l in old_content1.splitlines() if l.strip()]
                if username in lines1:
                    lines1.remove(username)
                    new_content1 = "\n".join(lines1)
                    await update_file(session, REPO, FILE_PATH, BRANCH, new_content1, sha1, f"remove {username}")

                # repo 2: tambah klo belum ada
                file_data2, status2, err2 = await fetch_file(session, REPO_2, FILE_PATH_2, BRANCH)
                if file_data2 is None:
                    await interaction.followup.send(embed=error_embed("Jika anda melihat pesan ini, hubungi admin!"), ephemeral=True)
                    return
                sha2 = file_data2.get("sha")
                old_content2 = base64.b64decode(file_data2.get("content", "").encode()).decode() if file_data2.get("content") else ""
                lines2 = [l.strip() for l in old_content2.splitlines() if l.strip()]
                if username not in lines2:
                    new_content2 = old_content2 + ("\n" if old_content2 and not old_content2.endswith("\n") else "") + username
                    status_update, resp_text = await update_file(session, REPO_2, FILE_PATH_2, BRANCH, new_content2, sha2, f"add {username}")
                    if status_update not in (200, 201):
                        await interaction.followup.send(embed=error_embed("Jika anda melihat pesan ini, hubungi admin!"), ephemeral=True)
                        return

        # update DB
        used_list.append(username)
        async with db_lock:
            cursor.execute("UPDATE keys SET used = ? WHERE key = ?", (json.dumps(used_list), key))
            cursor.execute("SELECT usernames FROM users WHERE user_id = ?", (uid,))
            res = cursor.fetchone()
            if res:
                usernames = json.loads(res[0])
                usernames.append(username)
                cursor.execute("UPDATE users SET usernames = ? WHERE user_id = ?", (json.dumps(usernames), uid))
            else:
                cursor.execute("INSERT INTO users (user_id,key,usernames) VALUES (?,?,?)", (uid,key,json.dumps([username])))
            conn.commit()


        await interaction.followup.send(embed=success_embed(f"Username `{username}` berhasil dipindahkan ke slot premium! Sisa slot: {total_slots-len(used_list)}"), ephemeral=True)

# ---------------- Manage Callback ----------------
async def manage_callback(interaction: discord.Interaction):
    uid = str(interaction.user.id)

    # ambil data user dari db
    async with db_lock:
        cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
        user_row = cursor.fetchone()
    if not user_row:
        await interaction.response.send_message(embed=error_embed("Kamu belum menambahkan username premium!"), ephemeral=True)
        return

    key, usernames_json = user_row
    usernames = json.loads(usernames_json) if usernames_json else []

    # ambil data key dari db
    cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
    key_row = cursor.fetchone()
    if not key_row:
        await interaction.response.send_message(embed=error_embed("Key tidak ditemukan!"), ephemeral=True)
        return

    total_slots, used_json = key_row
    used_list = json.loads(used_json) if used_json else []
    remaining_slots = total_slots - len(used_list)

    if not used_list:
        await interaction.response.send_message("Belum ada username yang bisa diedit.", ephemeral=True)
        return

    # buat embed
    def make_manage_embed():
        user_lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(used_list)) or " - "
        return make_embed(
            "Manage Akun Premium",
            f"✅ Username Roblox:\n{user_lines}\n\n🔑 Key: `{key}`\n\n⭐ Sisa slot: {remaining_slots}\n\nPilih username untuk diedit:"
        )

    view = View(timeout=None)
    options = [discord.SelectOption(label=u, description=f"Edit username {u}") for u in used_list]
    select = discord.ui.Select(placeholder="Pilih username", options=options, min_values=1, max_values=1)

    async def select_callback(inter: discord.Interaction):
        values = inter.data.get("values", [])
        if not values:
            await inter.response.send_message(embed=error_embed("Tidak ada username yang dipilih!"), ephemeral=True)
            return
        selected = values[0]
        await inter.response.send_modal(EditUsernameModal(key, selected))

    select.callback = select_callback
    view.add_item(select)

    await interaction.response.send_message(embed=make_manage_embed(), ephemeral=True, view=view)


# ---------------- Edit Username Modal (dengan auto-refresh) ----------------
class EditUsernameModal(Modal):
    def __init__(self, key, old_username):
        super().__init__(title=f"Edit Username ({old_username})")
        self.key = key
        self.old_username = old_username
        self.new_username = TextInput(label="Username Baru", placeholder="username baru...")
        self.add_item(self.new_username)

    async def on_submit(self, interaction: discord.Interaction):
        new_username = self.new_username.value.strip()
        if not new_username:
            await interaction.response.send_message(embed=error_embed("Username tidak boleh kosong!"), ephemeral=True)
            return

        # ambil data key
        async with db_lock:
            cursor.execute("SELECT used FROM keys WHERE key = ?", (self.key,))
            row = cursor.fetchone()
        if not row:
            await interaction.response.send_message(embed=error_embed("Key tidak ditemukan!"), ephemeral=True)
            return

        used_list = json.loads(row[0]) if row[0] else []
        if new_username in used_list:
            await interaction.response.send_message(embed=error_embed("Username sudah digunakan!"), ephemeral=True)
            return
        if self.old_username not in used_list:
            await interaction.response.send_message(embed=error_embed("Username lama tidak ada di key!"), ephemeral=True)
            return

        # update github di luar lock
        async with aiohttp.ClientSession() as session:
            file_data, status, err_text = await fetch_file(session, REPO_2, FILE_PATH_2, BRANCH)
            if file_data is None:
                await interaction.response.send_message(embed=error_embed("Jika anda melihat pesan ini, hubungi admin!"), ephemeral=True)
                return

            sha = file_data["sha"]
            old_content = base64.b64decode(file_data.get("content", "").encode()).decode() if file_data.get("content") else ""
            lines = [line.strip() for line in old_content.splitlines() if line.strip()]

            if self.old_username not in lines:
                await interaction.response.send_message(embed=error_embed("Username lama tidak ditemukan di slot premium!"), ephemeral=True)
                return

            lines[lines.index(self.old_username)] = new_username
            new_content = "\n".join(lines)
            await update_file(session, REPO_2, FILE_PATH_2, BRANCH, new_content, sha, f"edit {self.old_username} -> {new_username}")

        # update DB sekaligus
        used_list[used_list.index(self.old_username)] = new_username
        uid = str(interaction.user.id)
        async with db_lock:
            cursor.execute("UPDATE keys SET used = ? WHERE key = ?", (json.dumps(used_list), self.key))
            cursor.execute("SELECT usernames FROM users WHERE user_id = ?", (uid,))
            res = cursor.fetchone()
            if res:
                usernames = json.loads(res[0])
                if self.old_username in usernames:
                    usernames[usernames.index(self.old_username)] = new_username
                    cursor.execute("UPDATE users SET usernames = ? WHERE user_id = ?", (json.dumps(usernames), uid))
            conn.commit()

        await interaction.response.send_message(
            embed=make_embed(
                "Edit Username Sukses",
                f"✅ Username `{self.old_username}` diubah ke `{new_username}`!\n**Mohon menunggu beberapa menit setelah perubahan username!**",
                color=0x00FF00
            ),
            ephemeral=True
        )

class ResetKeyModal(Modal):
    def __init__(self, old_key=None):
        super().__init__(title="Reset Key")
        self.input_confirm = TextInput(
            label='Masukkan Key Baru',
            placeholder=old_key or "SansPrem_xxxxxxxxxxxxxx",
            max_length=29
        )
        self.add_item(self.input_confirm)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # biar aman

        uid = str(interaction.user.id)
        new_key = self.input_confirm.value.strip()

        async with db_lock:
            # ambil username + key lama
            cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                await interaction.followup.send(embed=error_embed("Kamu belum menambahkan username!"), ephemeral=True)
                return

            old_key, usernames_json = row
            usernames = json.loads(usernames_json) if usernames_json else []

            if not usernames:
                await interaction.followup.send(embed=error_embed("Username lama tidak ditemukan!"), ephemeral=True)
                return

            # cek key baru
            cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (new_key,))
            key_row = cursor.fetchone()
            if not key_row:
                await interaction.followup.send(embed=error_embed("Key baru tidak ditemukan di database!"), ephemeral=True)
                return

            slots, used_json = key_row
            used_list = json.loads(used_json) if used_json else []

            if used_list:
                await interaction.followup.send(embed=error_embed("Key baru sudah pernah digunakan!"), ephemeral=True)
                return

            if len(usernames) > slots:
                await interaction.followup.send(embed=error_embed(
                    f"Jumlah username lama ({len(usernames)}) melebihi slot key baru ({slots})!"
                ), ephemeral=True)
                return

            # update key baru dulu
            cursor.execute(
                "UPDATE keys SET used = ? WHERE key = ?",
                (json.dumps(usernames), new_key)
            )
            # update users
            cursor.execute("UPDATE users SET key = ? WHERE user_id = ?", (new_key, uid))
            conn.commit()

            # baru hapus key lama
            cursor.execute("DELETE FROM keys WHERE key = ?", (old_key,))
            conn.commit()

        await interaction.followup.send(
            embed=success_embed(
                f"Key berhasil di-reset!\nUsername lama telah dipindahkan ke key baru dengan {slots} slot.\nSilahkan lanjutkan menambahkan username jika slot masih tersisa."
            ),
            ephemeral=True
        )

# --------- Reset Key Callback ------------
async def reset_key_callback(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    async with db_lock:
        cursor.execute("SELECT key FROM users WHERE user_id = ?", (uid,))
        row = cursor.fetchone()
        old_key = row[0] if row else None
    await interaction.response.send_modal(ResetKeyModal(old_key))

class MyClient(discord.Client):
    async def setup_hook(self):
        asyncio.create_task(cleanup_old_keys())

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
tree = app_commands.CommandTree(client)

# ---------- Slash Commands ----------
@tree.command(name="generate-key", description="Generate key premium", guild=discord.Object(id=GUILD_ID))
async def generate_key(interaction: discord.Interaction, slots: int, keys: int = 1):
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message(embed=error_embed("Kamu tidak punya akses!"), ephemeral=True)
        print(f"Unauthorized user: @{interaction.user.display_name} id: {interaction.user.id}")
        return

    await interaction.response.defer(ephemeral=True)

    all_keys = []
    async with db_lock:
        now = time.time()
        for _ in range(keys):
            new_key = f"SansPrem_{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
            cursor.execute("INSERT INTO keys (key, slots, used, created_at) VALUES (?, ?, ?, ?)", 
                           (new_key, slots, "[]", now))
            all_keys.append(new_key)
        conn.commit()

    embed_key = discord.Embed(title="Keys Generated", color=0xA64DFF)
    embed_key.add_field(name="🔑 Keys:", value="\n".join(all_keys), inline=False)
    embed_key.add_field(name="🎟 Slots:", value=f"{slots}", inline=False)
    embed_key.add_field(name="👤 Admin:", value=f"<@{interaction.user.id}>", inline=False)
    await interaction.followup.send(embed=embed_key, ephemeral=True)

    print(f"Generated keys by user @{interaction.user.display_name} id: {interaction.user.id}:")
    for k in all_keys:
        print(k)

# ---------- Background Task ----------
async def cleanup_old_keys():
    await client.wait_until_ready()
    while not client.is_closed():
        cutoff = time.time() - 6*60*60
        async with db_lock:
            cursor.execute("SELECT key FROM keys WHERE used = ? AND created_at < ?", ("[]", cutoff))
            old_keys = [row[0] for row in cursor.fetchall()]
            for key in old_keys:
                cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
            if old_keys:
                conn.commit()
                print(f"Deleted old keys (1 menit test): {old_keys}")
        await asyncio.sleep(10*60)

# ---------- Message UI ----------
async def message_bot(channel, refresh_interval=300):
    
    message = None
    
    async def build_view():
    
        view = View(timeout=None)
        button_account = Button(label="Account Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
        button_premium = Button(label="Premium Info", style=discord.ButtonStyle.primary, emoji="⭐")
        button_manage = Button(label="Manage Accounts", style=discord.ButtonStyle.secondary, emoji="🛠️")
        button_reset_key = Button(label="Reset Key", style=discord.ButtonStyle.danger, emoji="🔄")

        # ------------- Account Info Callback -------------
        async def account_callback(interaction: discord.Interaction):
            uid = str(interaction.user.id)
            
            async with db_lock:
                cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
                user_row = cursor.fetchone()

            if not user_row:
                await interaction.response.send_modal(UsernameModal())
                return

            key = user_row[0]
            usernames = json.loads(user_row[1]) if user_row[1] else []

            async with db_lock:
                cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
                key_row = cursor.fetchone()
                
            if not key_row:
                await interaction.response.send_message(embed=error_embed("Key tidak ditemukan di database."), ephemeral=True)
                return

            total_slots = key_row[0]
            used_list = json.loads(key_row[1]) if key_row[1] else []
            remaining_slots = total_slots - len(used_list)
            user_lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(usernames)) or " - "

            embed = make_embed(
                "Info Akun Premium",
                f"✅ Username Roblox:\n{user_lines}\n\n🔑 Key: `{key}`\n\n⭐ Sisa slot: {remaining_slots}"
            )
            view2 = View()
            if remaining_slots > 0:
                add_btn = Button(label="Add Account", style=discord.ButtonStyle.success, emoji="➕")

                async def add_callback(inter: discord.Interaction):
                    await inter.response.send_modal(UsernameModal(key_slot=key))

                add_btn.callback = add_callback
                view2.add_item(add_btn)

            await interaction.response.send_message(embed=embed, ephemeral=True, view=view2)

        # ------------- Premium Info Callback -------------
        async def premium_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)  # mark interaction alive
            embed = make_embed(
                "Info Premium SansMoba",
                "⭐ Instant fish X5\n\n🕘 Script tanpa limit\n\n🔗 Webhook discord\n\n🎁 Dan masih banyak lagi!"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        button_account.callback = account_callback
        button_premium.callback = premium_callback
        button_manage.callback = manage_callback
        button_reset_key.callback = reset_key_callback
        

        view.add_item(button_account)
        view.add_item(button_premium)
        view.add_item(button_manage)
        view.add_item(button_reset_key)
        
        return view

    embed_main = make_embed(
        "SansMoba Premium",
        "• Klik **Account Info** untuk tambah dan info username premium\n• Klik **Premium Info** untuk melihat fitur\n• Klik **Manage Accounts** untuk reset username\n• Klik **Reset Key** untuk reset key\n",
    )
    embed_main.add_field(name="**📌 Note:**", value="**Jika terpental dari premium, silahkan masukkan username roblox + key terlebih dahulu**", inline=False)
    embed_main.add_field(name="**⚠️ Warning:**", value="**Reset key hanya untuk premium yang ingin menambah slot akun, jika ingin reset key silahkan open ticket**", inline=False)
    embed_main.set_footer(text="Pastikan username roblox benar (format: username) tanpa @")
    
    message = await channel.send(embed=embed_main, view=await build_view())
    
    while True:
        await asyncio.sleep(refresh_interval)
        await message.edit(embed=embed_main, view=await build_view())
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refreshed main message")

# ---------- on_ready ----------
@client.event
async def on_ready():
    print(f"Bot ready {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Commands synced")
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        client.loop.create_task(message_bot(channel))
    except Exception as e:
        print("Error sending main message:", e)

# --- Run ---
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GITHUB_TOKEN:
        print("Missing DISCORD_TOKEN or GITHUB_TOKEN")
        sys.exit(1)
    client.run(DISCORD_TOKEN)

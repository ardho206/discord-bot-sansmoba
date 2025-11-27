# bot.py (patched full)
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
from discord.ui import Button, View, Modal, TextInput, Select
from discord import app_commands
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# env
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_2 = os.getenv("GITHUB_REPO_2")
REPO_3 = os.getenv("GITHUB_REPO_3")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
FILE_PATH_2 = os.getenv("FILE_PATH_2")
FILE_PATH_3 = os.getenv("FILE_PATH_3")
BRANCH = os.getenv("BRANCH", "main")
GUILD_ID = int(os.getenv("GUILD_ID", "1360567703709941782"))
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS system_state (
    id INTEGER PRIMARY KEY,
    last_repo INTEGER
)
""")

cursor.execute("INSERT OR IGNORE INTO system_state (id,last_repo) VALUES (1,0)")
conn.commit()

db_lock = asyncio.Lock()
github_lock = asyncio.Lock()

# ---------- Embed builder ----------
API_BASE = "https://api.github.com"
def make_embed(title, desc, color=0xA64DFF):
    return discord.Embed(title=title, description=desc, color=color)

def error_embed(msg):
    return make_embed("Error", f"⚠️ {msg}", color=0xFF0000)

def success_embed(msg):
    return make_embed("Sukses", f"✅ {msg}", color=0x00FF00)

# --- Github helpers ---
async def fetch_file(session, repo, path, branch):
    try:
        path_enc = quote(path)
        url = f"{API_BASE}/repos/{repo}/contents/{path_enc}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        params = {"ref": branch}
        async with session.get(url, headers=headers, params=params, timeout=15) as r:
            text = await r.text()
            if r.status != 200:
                return None, r.status, text
            return await r.json(), r.status, None
    except Exception as e:
        return None, 0, str(e)

async def update_file(session, repo, path, branch, new_content, sha, message):
    try:
        path_enc = quote(path)
        url = f"{API_BASE}/repos/{repo}/contents/{path_enc}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        payload = {
            "message": message,
            "content": base64.b64encode(new_content.encode()).decode(),
            "branch": branch,
            "sha": sha
        }
        async with session.put(url, headers=headers, data=json.dumps(payload), timeout=30) as r:
            return r.status, await r.text()
    except Exception as e:
        return 0, str(e)

# util: decode content safely
def decode_content_field(file_data):
    if not file_data or not file_data.get("content"):
        return ""
    try:
        content = file_data["content"]
        if isinstance(content, str):
            return base64.b64decode(content.encode()).decode(errors="ignore")
        return ""
    except Exception:
        return ""

# ---------- Modal: Tambah Username ----------
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
        # defer karena ada operasi network + db
        await interaction.response.defer(ephemeral=True)

        username = self.username_input.value.strip()
        key = self.key_input.value.strip() if self.key_input else self.key_slot
        uid = str(interaction.user.id)

        if not username or not key:
            await interaction.followup.send(embed=error_embed("Username atau Key kosong!"), ephemeral=True)
            return

        # ambil key info (fast check)
        async with db_lock:
            cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
            key_row = cursor.fetchone()
        if not key_row:
            await interaction.followup.send(embed=error_embed("Key tidak valid!"), ephemeral=True)
            return

        slots = key_row[0]
        try:
            used_now_preview = json.loads(key_row[1] or "[]")
        except Exception:
            used_now_preview = []

        if len(used_now_preview) >= slots:
            await interaction.followup.send(embed=error_embed("Slot key habis!"), ephemeral=True)
            return

        # baca last_repo (determine target) - do NOT toggle yet
        async with db_lock:
            cursor.execute("SELECT last_repo FROM system_state WHERE id = 1")
            row = cursor.fetchone()
            last_repo = row[0] if row else 0

        target_repo_idx = 2 if last_repo == 0 else 3
        new_last_repo = 1 if last_repo == 0 else 0

        # perform github update to selected repo (under github_lock)
        async with github_lock:
            async with aiohttp.ClientSession() as session:
                repo = REPO_2 if target_repo_idx == 2 else REPO_3
                path = FILE_PATH_2 if target_repo_idx == 2 else FILE_PATH_3

                file_data, status, err = await fetch_file(session, repo, path, BRANCH)
                if file_data is None:
                    await interaction.followup.send(embed=error_embed(f"Gagal akses {repo} (status {status})"), ephemeral=True)
                    return

                sha = file_data.get("sha")
                old_content = decode_content_field(file_data)
                lines = [l.strip() for l in old_content.splitlines() if l.strip()]

                # append username if not exists (safety check)
                if username in lines:
                    # still proceed to DB update (maybe previous partial)
                    pass
                else:
                    new_content = old_content + ("\n" if old_content and not old_content.endswith("\n") else "") + username
                    st, resp = await update_file(session, repo, path, BRANCH, new_content, sha, f"add {username}")
                    if st not in (200, 201):
                        await interaction.followup.send(embed=error_embed(f"Update github gagal (status {st})"), ephemeral=True)
                        return

        # atomic DB update: re-check & update used and users and toggle system_state
        async with db_lock:
            cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
            key_row2 = cursor.fetchone()
            if not key_row2:
                await interaction.followup.send(embed=error_embed("Key hilang (race)"), ephemeral=True)
                return

            slots2 = key_row2[0]
            try:
                used_now = json.loads(key_row2[1] or "[]")
            except Exception:
                used_now = []

            if len(used_now) >= slots2:
                # somebody else took the slot meanwhile
                await interaction.followup.send(embed=error_embed("Slot habis (sudah dipakai orang lain)"), ephemeral=True)
                return

            # append username
            used_now.append(username)
            cursor.execute("UPDATE keys SET used = ? WHERE key = ?", (json.dumps(used_now), key))

            # update users table
            cursor.execute("SELECT usernames FROM users WHERE user_id = ?", (uid,))
            urow = cursor.fetchone()
            if urow:
                try:
                    user_list = json.loads(urow[0] or "[]")
                except:
                    user_list = []
                user_list.append(username)
                cursor.execute("UPDATE users SET usernames = ? WHERE user_id = ?", (json.dumps(user_list), uid))
            else:
                cursor.execute("INSERT INTO users (user_id, key, usernames) VALUES (?, ?, ?)", (uid, key, json.dumps([username])))

            # toggle repo state because github update sudah sukses
            cursor.execute("UPDATE system_state SET last_repo = ? WHERE id = 1", (new_last_repo,))
            conn.commit()

        await interaction.followup.send(embed=success_embed(f"Username `{username}` berhasil ditambahkan! Sisa slot: {slots2 - len(used_now)}"), ephemeral=True)


# ---------------- Manage Callback ----------------
async def manage_callback(interaction: discord.Interaction):
    uid = str(interaction.user.id)

    async with db_lock:
        cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
        user_row = cursor.fetchone()
    if not user_row:
        await interaction.response.send_message(embed=error_embed("Kamu belum menambahkan username premium!"), ephemeral=True)
        return

    key, usernames_json = user_row
    try:
        usernames = json.loads(usernames_json) if usernames_json else []
    except:
        usernames = []

    async with db_lock:
        cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
        key_row = cursor.fetchone()
    if not key_row:
        await interaction.response.send_message(embed=error_embed("Key tidak ditemukan!"), ephemeral=True)
        return

    total_slots = key_row[0]
    try:
        used_list = json.loads(key_row[1] or "[]")
    except:
        used_list = []

    if not used_list:
        await interaction.response.send_message("Belum ada username yang bisa diedit.", ephemeral=True)
        return

    # embed tetap sama, gua ga ubah
    def make_manage_embed():
        user_lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(used_list)) or " - "
        return make_embed(
            "Manage Akun Premium",
            f"✅ Username Roblox:\n{user_lines}\n\n🔑 Key: `{key}`\n\n⭐ Sisa slot: {total_slots - len(used_list)}\n\nPilih username untuk diedit:"
        )

    # gunakan pagination view
    view = ManagePagedView(key, used_list, page=0, embed_func=make_manage_embed)

    await interaction.response.send_message(
        embed=make_manage_embed(),
        ephemeral=True,
        view=view
    )

class ManagePagedView(View):
    PAGE_SIZE = 25

    def __init__(self, key, usernames, page, embed_func):
        super().__init__(timeout=None)
        self.key = key
        self.usernames = usernames
        self.page = page
        self.embed_func = embed_func

        self.max_page = max(0, (len(usernames) - 1) // self.PAGE_SIZE)

        self.add_dropdown()
        self.add_nav_buttons()

    # --- CREATE DROPDOWN BERDASARKAN PAGE ---
    def add_dropdown(self):
        start = self.page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        sliced = self.usernames[start:end]

        options = [
            discord.SelectOption(label=u, description=f"Edit username {u}")
            for u in sliced
        ]

        select = Select(
            placeholder=f"Pilih username (page {self.page+1}/{self.max_page+1})",
            options=options,
            min_values=1,
            max_values=1,
        )

        async def select_callback(inter: discord.Interaction):
            selected = inter.data["values"][0]
            await inter.response.send_modal(EditUsernameModal(self.key, selected))

        select.callback = select_callback
        self.add_item(select)

    # --- BUTTON NEXT & PREV ---
    def add_nav_buttons(self):
        prev_btn = Button(label="Prev", style=discord.ButtonStyle.secondary)
        next_btn = Button(label="Next", style=discord.ButtonStyle.primary)

        async def prev_callback(inter: discord.Interaction):
            if self.page > 0:
                self.page -= 1
            await self.refresh(inter)

        async def next_callback(inter: discord.Interaction):
            if self.page < self.max_page:
                self.page += 1
            await self.refresh(inter)

        prev_btn.callback = prev_callback
        next_btn.callback = next_callback

        self.add_item(prev_btn)
        self.add_item(next_btn)

    # --- REFRESH VIEW TANPA UBAH EMBED ---
    async def refresh(self, inter: discord.Interaction):
        new_view = ManagePagedView(self.key, self.usernames, self.page, self.embed_func)
        await inter.response.edit_message(
            embed=self.embed_func(),
            view=new_view
        )

# ---------------- Edit Username Modal (cek repo2 & repo3) ----------------
class EditUsernameModal(Modal):
    def __init__(self, key, old_username):
        super().__init__(title=f"Edit Username ({old_username})")
        self.key = key
        self.old_username = old_username
        self.new_username = TextInput(label="Username Baru", placeholder="username baru...")
        self.add_item(self.new_username)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        new_username = self.new_username.value.strip()
        if not new_username:
            await interaction.followup.send(embed=error_embed("Username tidak boleh kosong!"), ephemeral=True)
            return

        # ambil data key (fast)
        async with db_lock:
            cursor.execute("SELECT used FROM keys WHERE key = ?", (self.key,))
            row = cursor.fetchone()
        if not row:
            await interaction.followup.send(embed=error_embed("Key tidak ditemukan!"), ephemeral=True)
            return

        try:
            used_list = json.loads(row[0] or "[]")
        except Exception:
            used_list = []

        if new_username in used_list:
            await interaction.followup.send(embed=error_embed("Username sudah digunakan!"), ephemeral=True)
            return
        if self.old_username not in used_list:
            await interaction.followup.send(embed=error_embed("Username lama tidak ada di key!"), ephemeral=True)
            return

        # cari lokasi username di repo2 dulu, kalau nggak ada cek repo3
        target_repo = None
        target_path = None
        target_sha = None
        target_lines = None

        async with github_lock:
            async with aiohttp.ClientSession() as session:
                # repo2
                file2, status2, err2 = await fetch_file(session, REPO_2, FILE_PATH_2, BRANCH)
                if file2:
                    old2 = decode_content_field(file2)
                    lines2 = [l.strip() for l in old2.splitlines() if l.strip()]
                    if self.old_username in lines2:
                        target_repo = REPO_2
                        target_path = FILE_PATH_2
                        target_sha = file2.get("sha")
                        target_lines = lines2

                # repo3 if not found
                if target_repo is None:
                    file3, status3, err3 = await fetch_file(session, REPO_3, FILE_PATH_3, BRANCH)
                    if file3:
                        old3 = decode_content_field(file3)
                        lines3 = [l.strip() for l in old3.splitlines() if l.strip()]
                        if self.old_username in lines3:
                            target_repo = REPO_3
                            target_path = FILE_PATH_3
                            target_sha = file3.get("sha")
                            target_lines = lines3

                if target_repo is None:
                    await interaction.followup.send(embed=error_embed("Username lama tidak ditemukan di list manapun!"), ephemeral=True)
                    return

                # replace and push
                idx = target_lines.index(self.old_username)
                target_lines[idx] = new_username
                new_content = "\n".join(target_lines)

                st, resp = await update_file(session, target_repo, target_path, BRANCH, new_content, target_sha, f"edit {self.old_username} -> {new_username}")
                if st not in (200, 201):
                    await interaction.followup.send(embed=error_embed("Gagal update github!"), ephemeral=True)
                    return

        # now atomic DB update for keys/users
        async with db_lock:
            cursor.execute("SELECT used FROM keys WHERE key = ?", (self.key,))
            r = cursor.fetchone()
            if not r:
                await interaction.followup.send(embed=error_embed("Key hilang (race)"), ephemeral=True)
                return
            try:
                used_now = json.loads(r[0] or "[]")
            except:
                used_now = []

            # swap username
            if self.old_username in used_now:
                used_now[used_now.index(self.old_username)] = new_username
            else:
                await interaction.followup.send(embed=error_embed("Username lama tidak terdaftar (race)"), ephemeral=True)
                return

            cursor.execute("UPDATE keys SET used = ? WHERE key = ?", (json.dumps(used_now), self.key))

            uid = str(interaction.user.id)
            cursor.execute("SELECT usernames FROM users WHERE user_id = ?", (uid,))
            urow = cursor.fetchone()
            if urow:
                try:
                    ulist = json.loads(urow[0] or "[]")
                except:
                    ulist = []
                if self.old_username in ulist:
                    ulist[ulist.index(self.old_username)] = new_username
                    cursor.execute("UPDATE users SET usernames = ? WHERE user_id = ?", (json.dumps(ulist), uid))
            conn.commit()

        await interaction.followup.send(embed=success_embed(f"Username `{self.old_username}` diubah menjadi `{new_username}`!"), ephemeral=True)


# ---------------- Reset Key Modal (unchanged logic but safe) ----------------
class ResetKeyModal(Modal):
    def __init__(self, old_key=None):
        super().__init__(title="Reset Key")
        self.input_confirm = TextInput(
            label='Masukkan Key Baru',
            placeholder=old_key or "SansPrem_xxxxxxxxxxxxxx",
            max_length=64
        )
        self.add_item(self.input_confirm)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        new_key = self.input_confirm.value.strip()

        async with db_lock:
            cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                await interaction.followup.send(embed=error_embed("Kamu belum menambahkan username!"), ephemeral=True)
                return

            old_key, usernames_json = row
            try:
                usernames = json.loads(usernames_json) if usernames_json else []
            except:
                usernames = []

            if not usernames:
                await interaction.followup.send(embed=error_embed("Username lama tidak ditemukan!"), ephemeral=True)
                return

            cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (new_key,))
            key_row = cursor.fetchone()
            if not key_row:
                await interaction.followup.send(embed=error_embed("Key baru tidak ditemukan di database!"), ephemeral=True)
                return

            slots = key_row[0]
            used_json = key_row[1] or "[]"
            try:
                used_list = json.loads(used_json)
            except:
                used_list = []

            if used_list:
                await interaction.followup.send(embed=error_embed("Key baru sudah pernah digunakan!"), ephemeral=True)
                return

            if len(usernames) > slots:
                await interaction.followup.send(embed=error_embed(f"Jumlah username lama ({len(usernames)}) melebihi slot key baru ({slots})!"), ephemeral=True)
                return

            # update key baru
            cursor.execute("UPDATE keys SET used = ? WHERE key = ?", (json.dumps(usernames), new_key))
            cursor.execute("UPDATE users SET key = ? WHERE user_id = ?", (new_key, uid))
            conn.commit()

            cursor.execute("DELETE FROM keys WHERE key = ?", (old_key,))
            conn.commit()

        await interaction.followup.send(embed=success_embed(f"Key berhasil di-reset!"), ephemeral=True)


# --------- Reset Key Callback ------------
async def reset_key_callback(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    async with db_lock:
        cursor.execute("SELECT key FROM users WHERE user_id = ?", (uid,))
        row = cursor.fetchone()
        old_key = row[0] if row else None
    await interaction.response.send_modal(ResetKeyModal(old_key))


# ---------- Client + Commands ----------
class MyClient(discord.Client):
    async def setup_hook(self):
        asyncio.create_task(cleanup_old_keys())

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
tree = app_commands.CommandTree(client)

# ---------- generate-key slash ----------
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
    embed_key.add_field(name="🔑 Keys:", value="\n".join(all_keys) or "-", inline=False)
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
        cutoff = time.time() - 6*60*60  # 6 jam
        async with db_lock:
            cursor.execute("SELECT key FROM keys WHERE used = ? AND created_at < ?", ("[]", cutoff))
            old_keys = [row[0] for row in cursor.fetchall()]
            for key in old_keys:
                cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
            if old_keys:
                conn.commit()
                print(f"Deleted old keys: {old_keys}")
        await asyncio.sleep(10*60)  # 10 menit


# ---------- Message UI ----------
async def message_bot(channel, refresh_interval=300):
    message = None

    async def build_view():
        view = View(timeout=None)
        button_account = Button(label="Account Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
        button_premium = Button(label="Premium Info", style=discord.ButtonStyle.primary, emoji="⭐")
        button_manage = Button(label="Manage Accounts", style=discord.ButtonStyle.secondary, emoji="🛠️")
        button_reset_key = Button(label="Reset Key", style=discord.ButtonStyle.danger, emoji="🔄")

        async def account_callback(interaction: discord.Interaction):
            uid = str(interaction.user.id)
            async with db_lock:
                cursor.execute("SELECT key, usernames FROM users WHERE user_id = ?", (uid,))
                user_row = cursor.fetchone()

            if not user_row:
                # show modal to add username+key fast
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send_modal(UsernameModal())
                return

            await interaction.response.defer(ephemeral=True)

            key = user_row[0]
            try:
                usernames = json.loads(user_row[1] or "[]")
            except:
                usernames = []

            async with db_lock:
                cursor.execute("SELECT slots, used FROM keys WHERE key = ?", (key,))
                key_row = cursor.fetchone()

            if not key_row:
                await interaction.response.send_message(embed=error_embed("Key tidak ditemukan di database."), ephemeral=True)
                return

            total_slots = key_row[0]
            try:
                used_list = json.loads(key_row[1] or "[]")
            except:
                used_list = []

            remaining_slots = total_slots - len(used_list)
            user_lines = "\n".join(f"{i+1}. {u}" for i, u in enumerate(usernames)) or " - "

            embed = make_embed(
                "Info Akun Premium",
                f"✅ Username Roblox:\n{user_lines}\n\n🔑 Key: `{key}`\n\n⭐ Sisa slot: {remaining_slots}"
            )
            view2 = View(timeout=None)
            if remaining_slots > 0:
                add_btn = Button(label="Add Account", style=discord.ButtonStyle.success, emoji="➕")

                async def add_callback(inter: discord.Interaction):
                    await inter.response.send_modal(UsernameModal(key_slot=key))

                add_btn.callback = add_callback
                view2.add_item(add_btn)

            await interaction.followup.send(embed=embed, ephemeral=True, view=view2)

        async def premium_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
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

    try:
        message = await channel.send(embed=embed_main, view=await build_view())
    except Exception as e:
        print("Error sending main message:", e)
        return

    while True:
        await asyncio.sleep(refresh_interval)
        try:
            await message.edit(embed=embed_main, view=await build_view())
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refreshed main message")
        except Exception as e:
            print("Failed to refresh main message:", e)


# ---------- on_ready ----------
@client.event
async def on_ready():
    print(f"Bot ready {client.user}")
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Commands synced")
    except Exception as e:
        print("Failed to sync commands:", e)

    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        client.loop.create_task(message_bot(channel))
    except Exception as e:
        print("Error sending main message:", e)


# --- Run ---
if __name__ == "__main__":
    if not DISCORD_TOKEN or not (REPO_2 and REPO_3 and FILE_PATH_2 and FILE_PATH_3):
        print("Missing required environment variables (DISCORD_TOKEN or GITHUB repos/paths).")
        sys.exit(1)
    client.run(DISCORD_TOKEN)
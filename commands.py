import discord
import random
import string
import time
import json
from bot import get_helper_usage, increment_helper_usage

ALLOWED_ROLES_ID = [
    1431927807579000894, 
    1360568672149831700
]

GUILD_ID = 1360567703709941782
OWNER_ID = [938692894410297414, 1154602289097617450]
LOG_CHANNEL_ID = 1450939685701685401

HELPER_LIMIT = 10

def register_commands(tree, cursor, conn):

    @tree.command(
        name="generate-key",
        description="Generate key premium",
        guild=discord.Object(id=GUILD_ID)
    )
    async def generate_key(interaction: discord.Interaction, slots: int, keys: int = 1):
        await interaction.response.defer(ephemeral=True)

        uid = interaction.user.id
        now = time.time()

        # ================= OWNER MODE =================
        if uid in OWNER_ID:
            all_keys = []

            for _ in range(keys):
                new_key = f"SansPrem_{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
                cursor.execute(
                    "INSERT INTO keys (key, slots, used, created_at) VALUES (?, ?, ?, ?)",
                    (new_key, slots, '[]', now)
                )
                all_keys.append(new_key)

            conn.commit()

            embed_key = discord.Embed(
                title="🔑 Key Generated (OWNER MODE)",
                description="key berhasil dibuat tanpa batasan.",
                color=0xA64DFF
            )
            embed_key.add_field(name="🧩 Keys", value="\n".join(all_keys), inline=False)
            embed_key.add_field(name="🎟️ Slots", value=str(slots), inline=True)
            embed_key.add_field(name="👤 Admin", value=interaction.user.mention, inline=False)
            embed_key.set_footer(text="SansMoba System • owner generator")

            await interaction.followup.send(embed=embed_key, ephemeral=True)
            return

        # ================= HELPER MODE =================
        user_roles = [r.id for r in interaction.user.roles]
        if not any(role in user_roles for role in ALLOWED_ROLES_ID):
            em = discord.Embed(
                title="❌ Error",
                description="Kamu tidak memiliki akses",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        used = get_helper_usage(uid)
        if used + keys >= HELPER_LIMIT:
            em = discord.Embed(
                title="❌ Limit",
                description=f"Limit habis! {used}/{HELPER_LIMIT}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        all_keys = []

        for _ in range(keys):
            new_key = f"SansPrem_{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
            cursor.execute(
                "INSERT INTO keys (key, slots, used, created_at) VALUES (?, ?, ?, ?)",
                (new_key, slots, "[]", now)
            )
            all_keys.append(new_key)

        increment_helper_usage(uid, keys)

        conn.commit()

        log_ch = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_ch:
            log_embed = discord.Embed(
                title="🔔 Key Generated",
                description=(
                    f"👤 **Helper:** {interaction.user.mention}\n"
                    f"🎟️ **Slots per key:** `{slots}`\n"
                    f"🔑 **Jumlah key:** `{keys}`\n"
                    f"⌛ **Limit:** `{HELPER_LIMIT - (used + keys)}`\n"
                    f"📝 **Daftar key:**\n" + "\n".join(f"`{k}`" for k in all_keys)
                ),
                color=0x2ECC71
            )

            log_embed.set_footer(text="SansMoba • Key Generator Log")
            log_embed.timestamp = discord.utils.utcnow()

            await log_ch.send(embed=log_embed)

        embed_key = discord.Embed(
            title="🔑  Key Generated",
            color=0xA64DFF
        )
        embed_key.add_field(name="🧩  Keys", value="\n".join(all_keys), inline=False)
        embed_key.add_field(name="🎟️  Slots", value=str(slots), inline=True)
        embed_key.add_field(name="👤  Admin", value=interaction.user.mention, inline=False)
        embed_key.add_field(name="⌛  Limit", value=f"{HELPER_LIMIT - (used + keys)}/{HELPER_LIMIT}", inline=True)
        embed_key.set_footer(text="SansMoba System • premium key generator")

        await interaction.followup.send(embed=embed_key, ephemeral=True)

    @tree.command(
        name="key",
        description="cek detail key premium",
        guild=discord.Object(id=GUILD_ID)
    )
    async def key_check(interaction: discord.Interaction, key: str):
        await interaction.response.defer(ephemeral=True)

        user_roles = [r.id for r in interaction.user.roles]
        if not any(role in user_roles for role in ALLOWED_ROLES_ID):
            em = discord.Embed(
                title="❌  Error",
                description="Kamu tidak memiliki akses",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        cursor.execute("SELECT key, slots, used, created_at FROM keys WHERE key = ?", (key,))
        row = cursor.fetchone()

        if not row:
            em = discord.Embed(
                title="⚠️  Invalid Request",
                description=f"Key `{key}` tidak ditemukan",
                color=0xFF8800
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        key_str, slots, used_json, created_at = row

        import json
        try:
            used_list = json.loads(used_json or "[]")
        except:
            used_list = []

        cursor.execute("SELECT user_id, usernames FROM users WHERE key = ?", (key_str,))
        urow = cursor.fetchone()

        owner_text = "-"
        username_history = "-"
        username_count = 0

        if urow:
            disc_id, usernames_json = urow
            owner_text = f"<@{disc_id}>"

            try:
                ulist = json.loads(usernames_json or "[]")
            except:
                ulist = []

            username_history = "\n".join(ulist) if ulist else "-"
            username_count = max(0, len(ulist) - 1)

        em = discord.Embed(
            title="🔍  Key Information",
            color=0xA64DFF
        )

        em.add_field(name="🧩  Key", value=f"`{key_str}`", inline=False)
        em.add_field(name="🎟️  Slots", value=str(slots), inline=True)
        em.add_field(name="🖥️  HWID", value=str(len(used_list)), inline=True)

        em.add_field(name="👤  User", value=owner_text, inline=False)

        em.add_field(name="⌛  Riwayat username", value=username_history, inline=False)
        em.add_field(name="🔄  Total ganti username", value=str(username_count), inline=True)

        created_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_at))
        em.add_field(name="📅  Dibuat pada", value=created_text, inline=True)

        em.set_footer(text="SansMoba System • key inspector")

        await interaction.followup.send(embed=em, ephemeral=True)

    @tree.command(
        name="delete-key",
        description="hapus key premium",
        guild=discord.Object(id=GUILD_ID)
    )
    async def delete_key(interaction: discord.Interaction, key: str):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in OWNER_ID:
            em = discord.Embed(
                title="❌  Error",
                description="Kamu tidak memiliki akses",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        cursor.execute("SELECT key FROM keys WHERE key = ?", (key,))
        r = cursor.fetchone()

        if not r:
            em = discord.Embed(
                title="⚠️  Invalid Request",
                description=f"Key `{key}` tidak ditemukan",
                color=0xFF8800
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        cursor.execute("DELETE FROM keys WHERE key = ?", (key,))
        cursor.execute("DELETE FROM users WHERE key = ?", (key,))
        conn.commit()

        em = discord.Embed(
            title="🗑️  Deleted Key",
            description=f"Key `{key}` berhasil dihapus dari database.",
            color=0x00FF00
        )
        em.set_footer(text="SansMoba System • key deleted")

        await interaction.followup.send(embed=em, ephemeral=True)
        
    @tree.command(
        name="delete-username",
        description="hapus username dari key premium",
        guild=discord.Object(id=GUILD_ID)
    )
    async def delete_username(interaction: discord.Interaction, key: str, username: str):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in OWNER_ID:
            em = discord.Embed(
                title="error",
                description="kamu tidak memiliki akses",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        cursor.execute("SELECT key FROM keys WHERE key = ?", (key,))
        row_key = cursor.fetchone()
        if not row_key:
            em = discord.Embed(
                title="invalid",
                description=f"key `{key}` tidak ditemukan.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        cursor.execute("SELECT user_id, usernames FROM users WHERE key = ?", (key,))
        row_user = cursor.fetchone()
        if not row_user:
            em = discord.Embed(
                title="invalid",
                description=f"key `{key}` tidak terhubung ke user mana pun.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        user_id, usernames_json = row_user

        try:
            username_list = json.loads(usernames_json or "[]")
        except:
            username_list = []

        normalized = []
        if username_list and isinstance(username_list[0], dict):
            normalized = username_list
        else:
            for i, u in enumerate(username_list, start=1):
                normalized.append({"id": i, "username": u})

        lower = username.lower()
        found = None
        for item in normalized:
            if item["username"].lower() == lower:
                found = item
                break

        if not found:
            em = discord.Embed(
                title="not found",
                description=f"username `{username}` tidak ada di key `{key}`",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        normalized = [u for u in normalized if u["id"] != found["id"]]

        for i, item in enumerate(normalized, start=1):
            item["id"] = i

        cursor.execute(
            "UPDATE users SET usernames = ? WHERE user_id = ?",
            (json.dumps(normalized), user_id)
        )
        conn.commit()

        em = discord.Embed(
            title="berhasil",
            description=f"username `{username}` berhasil dihapus dari key `{key}`",
            color=0x00FF00
        )
        await interaction.followup.send(embed=em, ephemeral=True)
        
    @tree.command(
        name="reset",
        description="Reset limit helper",
        guild=discord.Object(id=GUILD_ID)
    )
    async def reset_limit(interaction: discord.Interaction, target: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id not in OWNER_ID:
            em = discord.Embed(
                title="❌  Error",
                description="Kamu tidak memiliki akses",
                color=0xFF0000
            )
            await interaction.followup.send(embed=em, ephemeral=True)
            return

        now = int(time.time())

        cursor.execute("""
            INSERT INTO helper_limits (discord_id, used_count, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (discord_id) 
            DO UPDATE SET
                used_count = 0,
                updated_at = ?
        """, (target.id, 0, now, now))

        conn.commit()

        em = discord.Embed(
            title="🎉  Success",
            description=f"Limit helper untuk {target.mention} berhasil direset",
            color=0x00FF00
        )
        await interaction.followup.send(embed=em, ephemeral=True)
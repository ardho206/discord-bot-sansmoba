# helpers.py
import time
import discord

HELPER_PRICE_MAP = {
    1: 35000,
    2: 50000,
    5: 100000,
    10: 150000,
    15: 200000
}

ALLOWED_ROLES_ID = [
    1431927807579000894,  # helper
    1360568672149831700,  # moderator
]

class HelperSystem:
    def __init__(self, client, cursor, conn):
        self.client = client
        self.cursor = cursor
        self.conn = conn

        self._prepare_tables()

    async def on_ready(self):
        print("Helper System ready")

    def _prepare_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS helpers (
            user_id TEXT PRIMARY KEY,
            saldo INTEGER DEFAULT 0
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS setor_temp (
            user_id TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            harga_per_bukti INTEGER DEFAULT 0,
            started_at REAL
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS verified_helpers (
            user_id TEXT PRIMARY KEY,
            channel_name TEXT
        )
        """)
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS setor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            count INTEGER,
            price INTEGER,
            total INTEGER,
            channel_name TEXT,
            created_at REAL
        )
        """)

        self.conn.commit()

    async def handle_helper_message(self, message):

        uid = str(message.author.id)
        content = (message.content or "").lower()
        channel = message.channel

        if not channel.name.startswith("【📑】・setor-"):
            return

        expected_channel = f"【📑】・setor-{message.author.name.lower()}"
        target = discord.utils.get(message.guild.text_channels, name=expected_channel)
        if channel.name != expected_channel:
            em = discord.Embed(
                title="🚫 Channel Salah",
                description=f"Gunakan channel {target.mention}",
                color=0xED4245
            )
            await message.reply(embed=em)
            return

        if content == ".verify":

            self.cursor.execute("SELECT channel_name FROM verified_helpers WHERE user_id = ?", (uid,))
            if self.cursor.fetchone():
                em = discord.Embed(
                    title="🔒 Sudah Terverifikasi",
                    description="Akun sudah terverifikasi sebelumnya",
                    color=0xED4245
                )
                await message.reply(embed=em)
                return

            self.cursor.execute("SELECT user_id FROM verified_helpers WHERE channel_name = ?", (channel.name,))
            if self.cursor.fetchone():
                em = discord.Embed(
                    title="🚫 Channel sudah digunakan",
                    description="Channel ini sudah terhubung dengan helper lain",
                    color=0xED4245
                )
                await message.reply(embed=em)
                return

            self.cursor.execute(
                "INSERT INTO verified_helpers(user_id, channel_name) VALUES (?, ?)",
                (uid, channel.name)
            )
            self.conn.commit()
            
            self.cursor.execute("SELECT saldo FROM helpers WHERE user_id = ?", (uid,))
            row = self.cursor.fetchone()
            
            if not row:
                self.cursor.execute(
                    "INSERT INTO helpers (user_id, saldo) VALUES (?, ?)",
                    (uid, 250000)
                )
                self.conn.commit()
                
            em = discord.Embed(
                title="🟢 Verifikasi berhasil",
                description=f"Akun {message.author.mention} berhasil dihubungkan!",
                color=0x57F287
            )
            await message.reply(embed=em)
            return

        if channel.name != f"【📑】・setor-{message.author.name.lower()}":
            await message.reply("**ini bukan channel setor kamu**")
            return

        if message.attachments:
            cur_count, harga = self.get_setor(uid)
            if cur_count is not None:
                c = self._count_images(message.attachments)
                if c > 0:
                    new_total = cur_count + c
                    self.add_setor_image(uid, new_total)
                    em = discord.Embed(
                        title="🖼️ Bukti diterima",
                        description=f"Jumlah bukti masuk: **{c}**\nTotal sekarang: **{new_total}**",
                        color=0x5865F2
                    )
                    await message.reply(embed=em)
    
        if not content.startswith("."):
            return
        
        setor_map = {
            ".setor": 35000,
            ".setor2": 50000,
            ".setor5": 100000,
            ".setor10": 150000,
            ".setor15": 200000
        }

        if content in setor_map:

            if not self.has_role(message.author, ALLOWED_ROLES_ID):
                em = discord.Embed(
                    title="🔒 Akses ditolak",
                    description="kamu bukan helper / mod / dev / owner.",
                    color=0xED4245
                )
                await message.reply(embed=em)
                return

            harga = setor_map[content]
            self.start_setor(uid, harga)

            em = discord.Embed(
                title="🟣 Session setor dibuka",
                color=0xA64DFF
            )
            em.add_field(name="💵 Harga per bukti", value=f"{harga:,}")
            em.add_field(
                name="📌 Instruksi",
                value="• Kirim semua bukti di channel ini\n• `.submit` untuk selesai\n• `.cancel` untuk batalkan",
                inline=False
            )
            await message.reply(embed=em)
            return

        if content == ".cancel":
            self.clear_setor(uid)
            em = discord.Embed(
                title="❌ Session dibatalkan",
                description="Session setor dibatalkan",
                color=0xED4245
            )
            await message.reply(embed=em)
            return

        if content == ".submit":
            cur_count, harga = self.get_setor(uid)
            if cur_count is None:
                await message.reply("**tidak ada setor session aktif**")
                return

            total = cur_count * harga
            self.add_saldo(uid, total)
            saldo_baru = self.get_saldo(uid)
            self.clear_setor(uid)
            self.save_history(uid, cur_count, harga, total, message.channel.name)

            em = discord.Embed(
                title="🟢Setor berhasil",
                color=0x57F287
            )
            em.add_field(name="📖 Jumlah bukti", value=str(cur_count), inline=False)
            em.add_field(name="💵 Harga per bukti", value=f"{harga:,}", inline=False)
            em.add_field(name="💰 Total", value=f"{total:,}", inline=False)
            em.add_field(name="📦 Saldo sekarang", value=f"{saldo_baru:,}", inline=False)

            await message.reply(embed=em)
            return

        if content == ".balance":
            saldo = self.get_saldo(uid)
            em = discord.Embed(
                title="💳 Saldo kamu",
                description=f"**{saldo:,}**",
                color=0xFEE75C
            )
            await message.reply(embed=em)
            return

        if content.startswith(".hlog"):
            
            try:
                limit = int(content.split(" ")[1])
            except:
                limit = 10
            
            limit = max(1, min(limit, 50))

            self.cursor.execute("""
                SELECT count, price, total, created_at, channel_name
                FROM setor_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (uid, limit))

            rows = self.cursor.fetchall()

            if not rows:
                await message.reply("**belum ada history setor**")
                return

            desc = ""
            for i, r in enumerate(rows, 1):
                count, price, total, ts, ch = r
                tgl = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
                desc += (
                    f"**{i}.** 📅 `{tgl}`\n"
                    f"• Bukti: **{count}**\n"
                    f"• Harga/bukti: **{price:,}**\n"
                    f"• Total: **{total:,}**\n"
                    f"• Channel: `{ch}`\n\n"
                )

            embed = discord.Embed(
                title=f"📜 History setor (last {limit})",
                description=desc,
                color=0xA64DFF
            )

            await message.reply(embed=embed)
            return

    @staticmethod
    def _count_images(files):
        c = 0
        for a in files:
            ct = a.content_type or ""
            fn = a.filename.lower()
            if ct.startswith("image/") or fn.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
                c += 1
        return c

    @staticmethod
    def has_role(member, allowed_ids):
        return any(r.id in allowed_ids for r in member.roles)

    def get_saldo(self, uid):
        self.cursor.execute("SELECT saldo FROM helpers WHERE user_id = ?", (uid,))
        r = self.cursor.fetchone()
        return r[0] if r else 0

    def set_saldo(self, uid, value):
        self.cursor.execute(
            "INSERT INTO helpers(user_id, saldo) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET saldo = excluded.saldo",
            (uid, value)
        )
        self.conn.commit()

    def add_saldo(self, uid, delta):
        now = self.get_saldo(uid)
        self.set_saldo(uid, now + delta)

    def start_setor(self, uid, harga):
        now = time.time()
        self.cursor.execute(
            "INSERT INTO setor_temp(user_id, count, harga_per_bukti, started_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET count = 0, harga_per_bukti = ?, started_at = ?",
            (uid, 0, harga, now, harga, now)
        )
        self.conn.commit()

    def get_setor(self, uid):
        self.cursor.execute("SELECT count, harga_per_bukti FROM setor_temp WHERE user_id = ?", (uid,))
        r = self.cursor.fetchone()
        return (r[0], r[1]) if r else (None, None)

    def add_setor_image(self, uid, total):
        self.cursor.execute("UPDATE setor_temp SET count = ? WHERE user_id = ?", (total, uid))
        self.conn.commit()

    def clear_setor(self, uid):
        self.cursor.execute("DELETE FROM setor_temp WHERE user_id = ?", (uid,))
        self.conn.commit()
        
    def save_history(self, uid, count, harga, total, channel_name):
        now = time.time()
        self.cursor.execute("""
            INSERT INTO setor_history(user_id, count, price, total, channel_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uid, count, harga, total, channel_name, now))
        self.conn.commit()

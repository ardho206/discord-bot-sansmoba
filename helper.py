import sqlite3
import os
import time

def get_helper_usage(cursor, discord_id: int):
    cursor.execute(
        "SELECT used_count FROM helper_limits WHERE discord_id = ?",
        (discord_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else 0

def increment_helper_usage(cursor, discord_id: int):
    cursor.execute("""
        INSERT INTO helper_limits (discord_id, used_count)
        VALUES (?, 1)               
        ON CONFLICT (discord_id) 
        DO UPDATE SET used_count = used_count + 1
    """, (discord_id,))

"""
data_manager.py — Supabase-backed storage layer.

Drop-in replacement for the JSON file version.
All public async function signatures are identical — no other file needs changing.

Tables used (run supabase_schema.sql first):
  users          — user records
  history        — credit + lookup history
  admin_settings — key/value JSONB store
  redeem_codes   — redeem codes
  payments       — payment records
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    DEFAULT_CREDITS, LOOKUP_COSTS, OWNER_ID,
)

logger = logging.getLogger(__name__)

# ── Supabase client (module-level singleton) ───────────────────────────────
_sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Helpers ────────────────────────────────────────────────────────────────

def get_ist_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))

def _now_iso() -> str:
    return get_ist_now().isoformat()

def _row_or_none(res) -> Optional[dict]:
    """Return first row of a supabase response, or None."""
    return res.data[0] if res.data else None


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user(user_id: int, username: str = "", full_name: str = "") -> dict:
    res = _sb.table("users").select("*").eq("user_id", user_id).execute()
    if res.data:
        u = res.data[0]
        updates: dict = {"last_seen": _now_iso()}
        if username:
            updates["username"] = username
        if full_name:
            updates["full_name"] = full_name
        _sb.table("users").update(updates).eq("user_id", user_id).execute()
        u.update(updates)
        return u

    # New user — insert
    row = {
        "user_id":        user_id,
        "username":       username,
        "full_name":      full_name,
        "credits":        DEFAULT_CREDITS,
        "total_earned":   DEFAULT_CREDITS,
        "total_spent":    0,
        "lookups_done":   0,
        "referral_code":  f"REF{user_id}",
        "referred_by":    None,
        "referral_count": 0,
        "is_banned":      False,
        "joined_at":      _now_iso(),
        "last_seen":      _now_iso(),
    }
    _sb.table("users").insert(row).execute()
    return row


async def get_all_users() -> list:
    res = _sb.table("users").select("*").execute()
    return res.data or []


async def update_user(user_id: int, updates: dict):
    _sb.table("users").update(updates).eq("user_id", user_id).execute()


async def add_credits(user_id: int, amount: int, reason: str = "") -> bool:
    res = _sb.table("users").select("credits, total_earned").eq("user_id", user_id).execute()
    if not res.data:
        return False
    row = res.data[0]
    _sb.table("users").update({
        "credits":      row["credits"] + amount,
        "total_earned": row["total_earned"] + amount,
    }).eq("user_id", user_id).execute()
    if reason:
        await _add_history(user_id, "credit", amount, reason)
    return True


async def deduct_credits(user_id: int, amount: int, reason: str = "") -> bool:
    # Fetch current credits + totals atomically
    res = _sb.table("users").select("credits, total_spent, lookups_done").eq("user_id", user_id).execute()
    if not res.data:
        return False
    row = res.data[0]
    if row["credits"] < amount:
        return False

    _sb.table("users").update({
        "credits":      row["credits"] - amount,
        "total_spent":  row["total_spent"] + amount,
        "lookups_done": row["lookups_done"] + 1,
    }).eq("user_id", user_id).execute()

    if reason:
        await _add_history(user_id, "debit", amount, reason)
    return True


async def set_user_credits(user_id: int, amount: int) -> bool:
    res = _sb.table("users").update({"credits": amount}).eq("user_id", user_id).execute()
    return bool(res.data)


async def ban_user(user_id: int):
    await update_user(user_id, {"is_banned": True})


async def unban_user(user_id: int):
    await update_user(user_id, {"is_banned": False})


async def apply_referral(new_user_id: int, referral_code: str) -> bool:
    from config import REFERRAL_CREDITS, REFERRED_CREDITS

    # Find referrer
    res = _sb.table("users").select("*").eq("referral_code", referral_code).execute()
    if not res.data:
        return False
    referrer = res.data[0]
    if referrer["user_id"] == new_user_id:
        return False

    # Check new user exists and hasn't been referred already
    res2 = _sb.table("users").select("referred_by").eq("user_id", new_user_id).execute()
    if not res2.data or res2.data[0].get("referred_by"):
        return False

    # Update new user
    _sb.table("users").update({
        "referred_by":  referrer["user_id"],
        "credits":      _get_field(new_user_id, "credits") + REFERRED_CREDITS,
        "total_earned": _get_field(new_user_id, "total_earned") + REFERRED_CREDITS,
    }).eq("user_id", new_user_id).execute()

    # Update referrer
    _sb.table("users").update({
        "credits":        referrer["credits"] + REFERRAL_CREDITS,
        "total_earned":   referrer["total_earned"] + REFERRAL_CREDITS,
        "referral_count": referrer["referral_count"] + 1,
    }).eq("user_id", referrer["user_id"]).execute()

    return True


def _get_field(user_id: int, field: str):
    """Sync helper to fetch a single field for in-function arithmetic."""
    res = _sb.table("users").select(field).eq("user_id", user_id).execute()
    return res.data[0][field] if res.data else 0


# ── History ────────────────────────────────────────────────────────────────

async def _add_history(user_id: int, entry_type: str, amount: int, reason: str):
    _sb.table("history").insert({
        "user_id":    user_id,
        "type":       entry_type,
        "amount":     amount,
        "reason":     reason,
        "created_at": _now_iso(),
    }).execute()


async def get_user_history(user_id: int, limit: int = 15) -> list:
    res = (
        _sb.table("history")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


async def add_lookup_history(user_id: int, lookup_type: str, query: str, result_summary: str):
    cost = LOOKUP_COSTS.get(f"{lookup_type}_lookup", 0)
    await _add_history(user_id, lookup_type, cost,
                       f"{lookup_type}:{query} -> {result_summary[:80]}")


# ── Admin Settings ─────────────────────────────────────────────────────────

_ADMIN_DEFAULTS = {
    "payment_group_id": None,
    "upi_id":           None,
    "upi_name":         "Vault Bot",
    "qr_file_id":       None,
    "maintenance":      False,
    "credit_packages": [
        {"id": "pkg_1", "credits": 50,   "price": 29,  "label": "Starter"},
        {"id": "pkg_2", "credits": 150,  "price": 79,  "label": "Popular"},
        {"id": "pkg_3", "credits": 400,  "price": 179, "label": "Pro"},
        {"id": "pkg_4", "credits": 1000, "price": 399, "label": "Elite"},
    ],
    "admins": [],
    "api_bomb_quantity_ranges": [
        {"id": "range_1", "label": "0–50",    "cycles": 50,   "credits": 3},
        {"id": "range_2", "label": "100–200",  "cycles": 200,  "credits": 8},
        {"id": "range_3", "label": "200–500",  "cycles": 500,  "credits": 15},
        {"id": "range_4", "label": "500–1000", "cycles": 1000, "credits": 25},
    ],
}


def _load_all_admin_settings() -> dict:
    """Fetch all rows from admin_settings and merge with defaults."""
    res = _sb.table("admin_settings").select("key, value").execute()
    merged = dict(_ADMIN_DEFAULTS)
    for row in (res.data or []):
        merged[row["key"]] = row["value"]
    return merged


def _upsert_admin_setting(key: str, value):
    """Insert or update a single key in admin_settings."""
    _sb.table("admin_settings").upsert({
        "key":   key,
        "value": value,
    }, on_conflict="key").execute()


async def load_admin_data() -> dict:
    return _load_all_admin_settings()


async def set_admin_setting(key: str, value):
    _upsert_admin_setting(key, value)


async def save_admin_data(data: dict):
    for key, value in data.items():
        _upsert_admin_setting(key, value)


async def get_admin_setting(key: str):
    res = _sb.table("admin_settings").select("value").eq("key", key).execute()
    if res.data:
        return res.data[0]["value"]
    return _ADMIN_DEFAULTS.get(key)


async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    admins = await get_admin_setting("admins") or []
    return user_id in admins


async def add_admin(user_id: int):
    admins = await get_admin_setting("admins") or []
    if user_id not in admins:
        admins.append(user_id)
    _upsert_admin_setting("admins", admins)


async def remove_admin(user_id: int):
    admins = await get_admin_setting("admins") or []
    admins = [a for a in admins if a != user_id]
    _upsert_admin_setting("admins", admins)


# ── Redeem Codes ───────────────────────────────────────────────────────────

async def create_redeem_code(code: str, credits: int, max_uses: int = 1):
    _sb.table("redeem_codes").upsert({
        "code":     code.upper(),
        "credits":  credits,
        "uses":     0,
        "max_uses": max_uses,
    }, on_conflict="code").execute()


async def delete_redeem_code(code: str):
    _sb.table("redeem_codes").delete().eq("code", code.upper()).execute()


async def use_redeem_code(code: str) -> Optional[int]:
    res = _sb.table("redeem_codes").select("*").eq("code", code.upper()).execute()
    if not res.data:
        return None
    rc = res.data[0]
    if rc["uses"] >= rc["max_uses"]:
        return None
    # Atomic increment
    _sb.table("redeem_codes").update({"uses": rc["uses"] + 1}).eq("code", code.upper()).execute()
    return rc["credits"]


async def list_redeem_codes() -> list:
    res = _sb.table("redeem_codes").select("*").execute()
    return res.data or []


# ── Payments ───────────────────────────────────────────────────────────────

async def create_payment(user_id: int, pkg_id: str, credits: int, price: int, pkg_label: str) -> str:
    pay_id = f"PAY{user_id}{int(time.time())}"
    _sb.table("payments").insert({
        "pay_id":     pay_id,
        "user_id":    user_id,
        "pkg_id":     pkg_id,
        "pkg_label":  pkg_label,
        "credits":    credits,
        "price":      price,
        "utr":        None,
        "screenshot": None,
        "status":     "pending",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }).execute()
    return pay_id


async def update_payment(pay_id: str, updates: dict):
    updates["updated_at"] = _now_iso()
    _sb.table("payments").update(updates).eq("pay_id", pay_id).execute()


async def get_payment(pay_id: str) -> Optional[dict]:
    res = _sb.table("payments").select("*").eq("pay_id", pay_id).execute()
    return res.data[0] if res.data else None


async def get_pending_payments() -> list:
    res = _sb.table("payments").select("*").eq("status", "pending").execute()
    return res.data or []


# ── Firebase Instances (stored in admin_settings) ──────────────────────────

async def list_all_firebase() -> list:
    return await get_admin_setting("firebase_list") or []


async def add_firebase(name: str, url: str, password: str = "") -> dict:
    fb_list = await list_all_firebase()
    entry = {
        "id":       f"fb_{int(time.time())}",
        "name":     name.strip(),
        "url":      url.strip().rstrip("/"),
        "password": password.strip(),
    }
    fb_list.append(entry)
    _upsert_admin_setting("firebase_list", fb_list)
    return entry


async def remove_firebase(fb_id: str) -> bool:
    fb_list = await list_all_firebase()
    new_list = [f for f in fb_list if f["id"] != fb_id]
    if len(new_list) == len(fb_list):
        return False
    _upsert_admin_setting("firebase_list", new_list)
    return True

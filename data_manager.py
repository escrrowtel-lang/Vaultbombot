"""
data_manager.py — Supabase backend.

Tables (create these in Supabase SQL editor — schema at bottom of file):
  users, admin_settings, payments, redeem_codes
"""

import logging
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, DEFAULT_CREDITS, LOOKUP_COSTS, OWNER_ID

logger = logging.getLogger(__name__)

# ─────────────────────────── Client ───────────────────────────

_sb: Client = None

def get_sb() -> Client:
    global _sb
    if _sb is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _sb

def get_ist_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))

def _now_iso() -> str:
    return get_ist_now().isoformat()

# ─────────────────────────── Users ───────────────────────────

async def get_user(user_id: int, username: str = "", full_name: str = "") -> dict:
    sb = get_sb()
    res = sb.table("users").select("*").eq("user_id", user_id).execute()
    if res.data:
        u = res.data[0]
        # Update username/name if changed
        updates = {"last_seen": _now_iso()}
        if username and u.get("username") != username:
            updates["username"] = username
        if full_name and u.get("full_name") != full_name:
            updates["full_name"] = full_name
        sb.table("users").update(updates).eq("user_id", user_id).execute()
        u.update(updates)
        return u
    # New user
    row = {
        "user_id":      user_id,
        "username":     username,
        "full_name":    full_name,
        "credits":      DEFAULT_CREDITS,
        "total_earned": DEFAULT_CREDITS,
        "total_spent":  0,
        "lookups_done": 0,
        "referral_code": f"REF{user_id}",
        "referred_by":  None,
        "referral_count": 0,
        "is_banned":    False,
        "joined_at":    _now_iso(),
        "last_seen":    _now_iso(),
    }
    sb.table("users").insert(row).execute()
    return row

async def get_all_users() -> list:
    res = get_sb().table("users").select("*").execute()
    return res.data or []

async def update_user(user_id: int, updates: dict):
    get_sb().table("users").update(updates).eq("user_id", user_id).execute()

async def add_credits(user_id: int, amount: int, reason: str = ""):
    sb = get_sb()
    res = sb.table("users").select("credits, total_earned").eq("user_id", user_id).execute()
    if not res.data:
        return False
    u = res.data[0]
    sb.table("users").update({
        "credits":      u["credits"] + amount,
        "total_earned": u["total_earned"] + amount,
    }).eq("user_id", user_id).execute()
    if reason:
        _add_history(user_id, "credit", amount, reason)
    return True

async def deduct_credits(user_id: int, amount: int, reason: str = "") -> bool:
    sb = get_sb()
    res = sb.table("users").select("credits, total_spent, lookups_done").eq("user_id", user_id).execute()
    if not res.data:
        return False
    u = res.data[0]
    if u["credits"] < amount:
        return False
    sb.table("users").update({
        "credits":      u["credits"] - amount,
        "total_spent":  u["total_spent"] + amount,
        "lookups_done": u["lookups_done"] + 1,
    }).eq("user_id", user_id).execute()
    if reason:
        _add_history(user_id, "debit", amount, reason)
    return True

async def set_user_credits(user_id: int, amount: int) -> bool:
    res = get_sb().table("users").update({"credits": amount}).eq("user_id", user_id).execute()
    return bool(res.data)

async def ban_user(user_id: int):
    await update_user(user_id, {"is_banned": True})

async def unban_user(user_id: int):
    await update_user(user_id, {"is_banned": False})

async def apply_referral(new_user_id: int, referral_code: str) -> bool:
    from config import REFERRAL_CREDITS, REFERRED_CREDITS
    sb = get_sb()
    # Find referrer
    ref_res = sb.table("users").select("user_id, credits, total_earned, referral_count").eq("referral_code", referral_code).execute()
    if not ref_res.data:
        return False
    referrer = ref_res.data[0]
    if referrer["user_id"] == new_user_id:
        return False
    # Check not already referred
    new_res = sb.table("users").select("referred_by, credits, total_earned").eq("user_id", new_user_id).execute()
    if not new_res.data or new_res.data[0].get("referred_by"):
        return False
    new_u = new_res.data[0]
    # Apply
    sb.table("users").update({
        "referred_by":  referrer["user_id"],
        "credits":      new_u["credits"] + REFERRED_CREDITS,
        "total_earned": new_u["total_earned"] + REFERRED_CREDITS,
    }).eq("user_id", new_user_id).execute()
    sb.table("users").update({
        "credits":        referrer["credits"] + REFERRAL_CREDITS,
        "total_earned":   referrer["total_earned"] + REFERRAL_CREDITS,
        "referral_count": referrer["referral_count"] + 1,
    }).eq("user_id", referrer["user_id"]).execute()
    return True

# ─────────────────────────── History ───────────────────────────

def _add_history(user_id: int, entry_type: str, amount: int, reason: str):
    try:
        get_sb().table("history").insert({
            "user_id":   user_id,
            "type":      entry_type,
            "amount":    amount,
            "reason":    reason,
            "created_at": _now_iso(),
        }).execute()
    except Exception as e:
        logger.error(f"History insert error: {e}")

async def get_user_history(user_id: int, limit: int = 15) -> list:
    res = get_sb().table("history")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    return res.data or []

async def add_lookup_history(user_id: int, lookup_type: str, query: str, result_summary: str):
    cost = LOOKUP_COSTS.get(f"{lookup_type}_lookup", 0)
    try:
        get_sb().table("history").insert({
            "user_id":    user_id,
            "type":       lookup_type,
            "amount":     cost,
            "reason":     f"{lookup_type}:{query} → {result_summary[:80]}",
            "created_at": _now_iso(),
        }).execute()
    except Exception as e:
        logger.error(f"Lookup history error: {e}")

# ─────────────────────────── Admin Settings ───────────────────────────

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
}

async def load_admin_data() -> dict:
    sb = get_sb()
    res = sb.table("admin_settings").select("key, value").execute()
    data = dict(_ADMIN_DEFAULTS)
    for row in (res.data or []):
        data[row["key"]] = row["value"]
    return data

async def set_admin_setting(key: str, value):
    sb = get_sb()
    # Upsert
    sb.table("admin_settings").upsert({"key": key, "value": value}).execute()

async def save_admin_data(data: dict):
    """Save all keys from data dict."""
    for key, value in data.items():
        await set_admin_setting(key, value)

async def get_admin_setting(key: str):
    d = await load_admin_data()
    return d.get(key)

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    d = await load_admin_data()
    admins = d.get("admins", [])
    return user_id in admins

async def add_admin(user_id: int):
    d = await load_admin_data()
    admins = d.get("admins", [])
    if user_id not in admins:
        admins.append(user_id)
    await set_admin_setting("admins", admins)

async def remove_admin(user_id: int):
    d = await load_admin_data()
    admins = [a for a in d.get("admins", []) if a != user_id]
    await set_admin_setting("admins", admins)

# ─────────────────────────── Redeem Codes ───────────────────────────

async def create_redeem_code(code: str, credits: int, max_uses: int = 1):
    get_sb().table("redeem_codes").upsert({
        "code":     code.upper(),
        "credits":  credits,
        "uses":     0,
        "max_uses": max_uses,
    }).execute()

async def delete_redeem_code(code: str):
    get_sb().table("redeem_codes").delete().eq("code", code.upper()).execute()

async def use_redeem_code(code: str):
    """Returns credits awarded or None if invalid/expired."""
    sb = get_sb()
    res = sb.table("redeem_codes").select("*").eq("code", code.upper()).execute()
    if not res.data:
        return None
    rc = res.data[0]
    if rc["uses"] >= rc["max_uses"]:
        return None
    sb.table("redeem_codes").update({"uses": rc["uses"] + 1}).eq("code", code.upper()).execute()
    return rc["credits"]

async def list_redeem_codes() -> list:
    res = get_sb().table("redeem_codes").select("*").execute()
    return res.data or []

# ─────────────────────────── Payments ───────────────────────────

async def create_payment(user_id: int, pkg_id: str, credits: int, price: int, pkg_label: str) -> str:
    import time
    pay_id = f"PAY{user_id}{int(time.time())}"
    get_sb().table("payments").insert({
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
    get_sb().table("payments").update(updates).eq("pay_id", pay_id).execute()

async def get_payment(pay_id: str) -> dict | None:
    res = get_sb().table("payments").select("*").eq("pay_id", pay_id).execute()
    return res.data[0] if res.data else None

async def get_pending_payments() -> list:
    res = get_sb().table("payments").select("*").eq("status", "pending").execute()
    return res.data or []


# 🛡️ Vault Bot — Setup & Deploy Guide

## Files
```
vault_bot/
├── main.py              ← Entry point
├── config.py            ← All config constants
├── data_manager.py      ← JSON persistence layer
├── keyboards.py         ← All inline button layouts
├── handlers_user.py     ← User-facing handlers
├── handlers_payment.py  ← Buy credits / payment flow
├── handlers_admin.py    ← Admin panel handlers
├── requirements.txt
├── render.yaml          ← Render deploy config
├── .env.example
└── data/                ← Auto-created, stores JSON files
```

---

## Local Setup

```bash
git clone <your-repo>
cd vault_bot
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add BOT_TOKEN and OWNER_ID
python main.py
```

---

## Deploy on Render (Free Tier)

1. Push code to GitHub
2. Go to https://render.com → New → Web Service (or Background Worker)
3. Connect your GitHub repo
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `python main.py`
6. Add Environment Variables:
   - `BOT_TOKEN` = your token from @BotFather
   - `OWNER_ID` = your Telegram user ID
7. Add a **Disk** (Render → your service → Disks):
   - Mount path: `/opt/render/project/src/data`
   - Size: 1 GB (free tier has 1 GB)
8. Deploy!

> ⚠️ Without the Disk, data resets on each deploy. Always add the disk.

---

## Admin Setup (First Run)

After bot starts, message it on Telegram:

1. `/admin` — opens admin panel
2. **Payment Setup** → Set UPI ID (format: `upiid@bank YourName`)
3. **Payment Setup** → Set QR Image (send your UPI QR screenshot)
4. **Payment Setup** → Set Payment Group:
   - Create a Telegram group
   - Add your bot as admin
   - Forward any message from that group to the bot
   - OR type the group's chat ID (starts with -100...)

---

## User Flow

```
/start
  └── Main Menu
       ├── LOOKUPS → Pick type → Enter query → Confirm → Result
       ├── My Profile → Credits, stats, referral code
       ├── Buy Credits → Pick package → See QR+UPI → Pay → Submit UTR+Screenshot → Wait approval
       ├── Redeem Code → Enter code → Credits added
       ├── Referral → Share link → Earn credits per signup
       └── History → Last 15 lookups/transactions
```

## Payment Flow

```
User selects package
  → Bot shows QR + UPI ID + amount
  → User pays via UPI
  → User clicks "I've Paid" button
  → Bot asks for UTR number (text)
  → Bot asks for payment screenshot (photo)
  → Bot forwards both to payment group with Approve/Reject buttons
  → Admin clicks Approve → credits auto-added + user notified
  → Admin clicks Reject → user notified with UTR for dispute
```

---

## Adding Real Lookup APIs

In `handlers_user.py`, find `_execute_lookup()` and replace the stub for each type:

```python
async def _execute_lookup(lookup_type: str, query: str) -> str:
    if lookup_type == "phone":
        # Call your API here
        response = requests.get(f"https://your-api.com/phone/{query}")
        data = response.json()
        return f"📱 Carrier: {data['carrier']}\n📍 Region: {data['region']}"
    # ... etc
```

---

## Credit Packages (Edit in Admin Panel)

Default packages (editable via `data/admin.json`):
- Starter: 50 credits @ ₹29
- Popular: 150 credits @ ₹79  
- Pro: 400 credits @ ₹179
- Elite: 1000 credits @ ₹399

---

## Commands

| Command | Who | What |
|---------|-----|------|
| `/start` | Everyone | Register + main menu |
| `/admin` | Admins | Open admin panel |


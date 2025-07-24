import json
import requests
import asyncio
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WALLET_FILE = "wallet_store.json"
SEEN_FILLS = {}
KNOWN_ORDERS = {}

def load_wallets():
    try:
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_wallets(wallets):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallets, f)

async def add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = context.args[0].lower()
    wallets = load_wallets()
    if wallet in wallets:
        await update.message.reply_text("Wallet already followed.")
    else:
        wallets.append(wallet)
        save_wallets(wallets)
        await update.message.reply_text(f"Added wallet: {wallet}")

async def remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = context.args[0].lower()
    wallets = load_wallets()
    if wallet not in wallets:
        await update.message.reply_text("Wallet not found.")
    else:
        wallets.remove(wallet)
        save_wallets(wallets)
        await update.message.reply_text(f"Removed wallet: {wallet}")

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallets = load_wallets()
    if not wallets:
        await update.message.reply_text("No wallets followed.")
    else:
        msg = "📋 Followed wallets:\n" + "\n".join(wallets)
        await update.message.reply_text(msg)

def get_fills(wallet):
    try:
        response = requests.post("https://api.hyperliquid.xyz/info", json={
            "type": "getFills",
            "user": wallet
        }, timeout=10)
        return response.json().get("fills", [])
    except Exception as e:
        print(f"[getFills] Error for {wallet}: {e}")
        return []

def get_open_orders(wallet):
    try:
        response = requests.post("https://api.hyperliquid.xyz/info", json={
            "type": "getOpenOrders",
            "user": wallet
        }, timeout=10)
        return response.json().get("orders", [])
    except Exception as e:
        print(f"[getOpenOrders] Error for {wallet}: {e}")
        return []

def format_fill(fill, wallet):
    is_perp = fill.get("crossed", False)
    side = fill.get("side", "")
    coin = fill.get("coin", "")
    px = fill.get("px", "")
    sz = fill.get("sz", "")
    time = fill.get("time", "")

    label = "🟢" if side == "Buy" else "🔴"
    trade_type = "PERP" if is_perp else "SPOT"
    direction = "BUY" if side == "Buy" else "SELL"

    return f"""
👤 `{wallet}`
{label} *{trade_type} {direction}* `{coin}`
Price: {px} USDC
Size: {sz}
Time: {time}
"""

def format_order(order, wallet, status):
    # status = "placed" or "cancelled"
    coin = order.get("coin", "")
    px = order.get("px", "")
    sz = order.get("sz", "")
    side = order.get("side", "")
    isPerp = order.get("isPositionTpsl", False) or coin.endswith("PERP") or order.get("reduceOnly", False)

    label = "📥" if status == "placed" else "❌"
    direction = "BUY" if side == "Buy" else "SELL"
    trade_type = "PERP" if isPerp else "SPOT"

    return f"""
👤 `{wallet}`
{label} *{trade_type} {direction} Order {status.upper()}*
Size: {sz}
Price: {px} USDC
"""

async def monitor(app):
    while True:
        wallets = load_wallets()
        for wallet in wallets:
            # Track fills
            fills = get_fills(wallet)
            for fill in fills:
                fid = fill.get("fillId")
                if fid and fid not in SEEN_FILLS.setdefault(wallet, set()):
                    msg = format_fill(fill, wallet)
                    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                    SEEN_FILLS[wallet].add(fid)

            # Track orders
            current_orders = get_open_orders(wallet)
            current_ids = set(o["oid"] for o in current_orders)
            previous_ids = KNOWN_ORDERS.get(wallet, set())

            # New orders
            new_ids = current_ids - previous_ids
            for oid in new_ids:
                order = next((o for o in current_orders if o["oid"] == oid), None)
                if order:
                    msg = format_order(order, wallet, "placed")
                    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

            # Cancelled orders
            cancelled_ids = previous_ids - current_ids
            for oid in cancelled_ids:
                order = {"oid": oid}
                msg = format_order(order, wallet, "cancelled")
                await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

            KNOWN_ORDERS[wallet] = current_ids

        await asyncio.sleep(10)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("add", add_wallet))
    app.add_handler(CommandHandler("remove", remove_wallet))
    app.add_handler(CommandHandler("list", list_wallets))

    async def start_background_tasks(application):
    asyncio.create_task(monitor(application))
    
    app.post_init = start_background_tasks
    
    print("Bot running...")
    app.run_polling()


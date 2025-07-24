import time, json, requests, asyncio, os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WALLET_FILE = "wallet_store.json"
SEEN = {}

def load_wallets():
    try:
        return json.load(open(WALLET_FILE))
    except:
        return []

def save_wallets(w):
    with open(WALLET_FILE, "w") as f:
        json.dump(w, f)

async def add_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    w = ctx.args[0].lower()
    wallets = load_wallets()
    if w in wallets:
        await update.message.reply_text("Wallet already tracked.")
    else:
        wallets.append(w)
        save_wallets(wallets)
        await update.message.reply_text(f"Tracking {w}")

async def remove_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    w = ctx.args[0].lower()
    wallets = load_wallets()
    if w not in wallets:
        await update.message.reply_text("Wallet not found.")
    else:
        wallets.remove(w)
        save_wallets(wallets)
        await update.message.reply_text(f"Stopped tracking {w}")

async def list_wallets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wallets = load_wallets()
    msg = "Tracked wallets:\n" + ("\n".join(wallets) if wallets else "None")
    await update.message.reply_text(msg)

def get_fills(wallet):
    try:
        resp = requests.post("https://api.hyperliquid.xyz/info", json={
            "type": "getFills", "user": wallet
        }, timeout=10)
        return resp.json().get("fills", [])
    except Exception as e:
        print("Error:", e)
        return []

def format_fill(fill, wallet):
    side = "🟢 LONG" if fill["side"] == "Buy" else "🔴 SHORT"
    return f"{wallet}\n{side} {fill['coin']}\nPrice: {fill['px']} USDC\nSize: {fill['sz']}\nTime: {fill['time']}"

async def monitor(app):
    while True:
        wallets = load_wallets()
        for w in wallets:
            fills = get_fills(w)
            for f in fills:
                fid = f.get("fillId")
                if fid and fid not in SEEN.setdefault(w, set()):
                    await app.bot.send_message(chat_id=CHAT_ID, text=format_fill(f, w), parse_mode="Markdown")
                    SEEN[w].add(fid)
        await asyncio.sleep(10)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("add", add_wallet))
    app.add_handler(CommandHandler("remove", remove_wallet))
    app.add_handler(CommandHandler("list", list_wallets))
    asyncio.create_task(monitor(app))
    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

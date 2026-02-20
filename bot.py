cd ~/topping-bot && cat > bot.py << 'EOF'
import os, json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
HAMID_ID = int(os.getenv("HAMID_ID", "722627622"))
FALLON_ID = int(os.getenv("FALLON_ID", "0"))

DEPT_MGR = {"IT":722627622,"MARKETING":722627622,"OPS":722627622,"SALES":722627622}
DATA_FILE = "tickets.json"

def load_data():
    if not os.path.exists(DATA_FILE): return {"tickets":{},"daily_counter":{}}
    with open(DATA_FILE) as f: return json.load(f)

def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f,indent=2)

def make_id(prefix):
    today=datetime.now().strftime("%Y%m%d"); d=load_data()
    d["daily_counter"].setdefault(today,0); d["daily_counter"][today]+=1
    save_data(d); return f"{prefix}-{today}-{str(d['daily_counter'][today]).zfill(4)}"

async def start(u,c): await u.message.reply_text("Send your task message.")
async def show_id(u,c): await u.message.reply_text(f"Your ID: {u.effective_user.id}")

async def on_message(u,c):
    if u.effective_chat.type!="private": return
    c.user_data["draft"]=u.message.text
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("IT",callback_data="D_IT")],[InlineKeyboardButton("Marketing",callback_data="D_MARKETING")],[InlineKeyboardButton("Operations",callback_data="D_OPS")],[InlineKeyboardButton("Sales",callback_data="D_SALES")]])
    await u.message.reply_text("Select department:",reply_markup=kb)

async def on_dept(u,c):
    q=u.callback_query; await q.answer()
    dept=q.data.replace("D_","")
    if dept not in DEPT_MGR: await q.edit_message_text("Unknown."); return
    mgr=DEPT_MGR[dept]; tid=make_id(dept)
    txt=c.user_data.get("draft","")
    d=load_data(); d["tickets"][tid]={"staff_id":u.effective_user.id,"manager_id":mgr,"status":"OPEN"}; save_data(d)
    msg=f"New Ticket: {tid}\nFrom: {u.effective_user.full_name}\nDept: {dept}\n\n{txt}"
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("In Progress",callback_data=f"S_p_{tid}"),InlineKeyboardButton("Done",callback_data=f"S_d_{tid}")]])
    try: await c.bot.send_message(mgr,msg,reply_markup=kb)
    except: pass
    await q.edit_message_text(f"Ticket created: {tid}")

async def on_status(u,c):
    q=u.callback_query; await q.answer()
    parts=q.data.split("_",2)
    if len(parts)<3: return
    action,tid=parts[1],parts[2]
    d=load_data(); t=d["tickets"].get(tid)
    if not t: return
    if u.effective_user.id!=t["manager_id"]: await q.answer("Not authorized.",show_alert=True); return
    t["status"]="IN_PROGRESS" if action=="p" else "DONE"; save_data(d)
    await q.edit_message_text(f"{'🟡' if action=='p' else '🟢'} {tid} — {t['status']}")

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("id",show_id))
    app.add_handler(CallbackQueryHandler(on_dept,pattern=r"^D_"))
    app.add_handler(CallbackQueryHandler(on_status,pattern=r"^S_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE&filters.TEXT&~filters.COMMAND,on_message))
    print("Bot running.")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
EOF

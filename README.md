# Topping Internal Operations Bot

یک سیستم مدیریت Task داخلی برای تلگرام — ساخته شده برای تیم Topping.

---

## راه‌اندازی سریع

### ۱. پیش‌نیازها
- Python 3.11+
- یه VPS یا Railway یا Render

### ۲. نصب

```bash
git clone <repo>
cd topping-bot
pip install -r requirements.txt
```

### ۳. تنظیم محیط

```bash
cp .env.example .env
# فایل .env رو باز کن و مقادیر رو پر کن
```

### ۴. ساخت ربات در تلگرام
۱. به @BotFather برو
۲. `/newbot` بزن
۳. Token رو در .env بذار

### ۵. ساخت گروه‌ها و گرفتن Chat ID
۱. سه گروه بساز: Tasks Hub، General، GM Dashboard
۲. ربات رو به هر سه گروه اضافه کن (به عنوان Admin)
۳. یه پیام توی هر گروه بفرست
۴. این لینک رو باز کن:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
۵. Chat IDها رو پیدا کن و در .env بذار

### ۶. اجرا

```bash
python bot.py
```

---

## دستورات

| دستور | توضیح | مثال |
|-------|-------|------|
| `/task DEPT description` | ساخت task جدید | `/task IT سایت بالا نمیاد` |
| `/status` | نمایش taskهای باز | `/status` |
| `/announce message` | ارسال اطلاعیه به همه | `/announce جلسه فردا ۱۰ صبح` |

### دپارتمان‌ها
- `IT`
- `MARKETING`
- `OPS`
- `RD`
- `GENERAL`

### دکمه‌های Lifecycle
- 🟡 **In Progress** — task شروع شده
- 🟢 **Done** — task تموم شده
- 👤 **Assign to Me** — این task رو برمیدارم
- 🔁 **Escalate** — نیاز به توجه مدیر داره

### آپلود فایل
برای وصل کردن فایل (PDF، عکس، سند) به یه task:
۱. پیام task رو Reply کن
۲. فایل رو بفرست
۳. ربات فایل رو به اون task وصل می‌کنه

---

## ساختار پروژه

```
topping-bot/
├── bot.py                  # نقطه شروع
├── requirements.txt
├── .env.example
├── database/
│   ├── db.py               # SQLite layer
│   └── topping_ops.db      # ساخته میشه خودکار
├── handlers/
│   ├── task_handler.py     # /task و /status
│   ├── callback_handler.py # دکمه‌های inline
│   ├── file_handler.py     # آپلود فایل
│   └── announce_handler.py # /announce
├── utils/
│   └── formatter.py        # قالب‌بندی پیام‌ها
└── storage/
    └── task_*/             # فایل‌های آپلود شده
```

---

## Deploy روی Railway

```bash
railway login
railway init
railway up
```

Environment variables رو توی Railway dashboard بذار.

---

## نسخه‌های بعدی
- [ ] Web Dashboard
- [ ] KPI Analytics
- [ ] AI Priority Scoring

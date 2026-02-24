# عیب‌یابی ربات (بدون GitHub و Render)

## 0) از همون فولدر درست اجرا می‌کنی؟

```bash
cd /Users/hamidrezazebardast/topping-bot
pwd
ls -la
```

باید `bot.py` و `.env` را همینجا ببینی.

---

## 1) رایج‌ترین علت: venv فعال نیست / پکیج‌ها نصب نیست

```bash
cd /Users/hamidrezazebardast/topping-bot
python3 -m venv venv
source venv/bin/activate
python -V
pip -V
pip install -r requirements.txt
```

بعد اجرا:

```bash
python bot.py
```

اگر ارور داد، همون ارور را مستقیم می‌بینی.

---

## 2) .env لود نمی‌شود (BOT_TOKEN not set)

قبل از اجرای bot این تست را بزن:

```bash
cd /Users/hamidrezazebardast/topping-bot
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('BOT_TOKEN?', bool(os.getenv('BOT_TOKEN'))); print('HAMID_ID', os.getenv('HAMID_ID'))"
```

اگر `BOT_TOKEN? False` بود → یعنی `.env` درست نیست یا لود نمی‌شود.

مطمئن شو فایل `.env` دقیقاً داخل همین پوشه است و این خط داخلش هست:

```
BOT_TOKEN=xxxxx
```

---

## 3) ربات اجرا می‌شود ولی «پاسخ نمی‌دهد» (Conflict / دو تا ربات روشن)

همه را خاموش کن:

```bash
pkill -f "python.*bot.py"
```

بعد فقط یکی اجرا کن:

```bash
cd /Users/hamidrezazebardast/topping-bot
source venv/bin/activate
python bot.py
```

---

## 4) وقتی ترمینال بسته می‌شود ربات می‌خوابد

**روش ساده: nohup**

```bash
cd /Users/hamidrezazebardast/topping-bot
source venv/bin/activate
nohup python bot.py > bot.log 2>&1 &
```

چک کن بالا آمده یا نه:

```bash
ps aux | grep -i "python.*bot.py" | grep -v grep
tail -n 60 bot.log
```

**روش حرفه‌ای: pm2**

```bash
npm i -g pm2
cd /Users/hamidrezazebardast/topping-bot
pm2 start bot.py --interpreter ./venv/bin/python --name topping-bot
pm2 logs topping-bot
pm2 save
```

---

## ارور: `AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'`

این باگ **python-telegram-bot 20.7** روی **Python 3.13+** است (و روی Python 3.14 روی Render). رفعش:

**لوکال:**
```bash
pip install "python-telegram-bot[job-queue]>=20.9"
```
(در `requirements.txt` هم نسخه را به `>=20.9` تغییر داده‌ایم.)

**روی Render:** اگر لاگ Render این ارور را نشان می‌دهد:
1. در ریشه پروژه فایل **`.python-version`** بساز با محتوای یک خط: `3.12` (تا Render با Python 3.12 اجرا کند، نه 3.14).
2. مطمئن شو `requirements.txt` شامل `python-telegram-bot[job-queue]>=20.9` است.
3. کد فعلی را push کن (همان bot.py که در لوکال داری با `BOT VERSION: 2026-02-23 IT-ROUTING v1`). اگر روی Render هنوز "Database initialized" یا "Starting Topping Ops bot worker" می‌بینی یعنی نسخه قدیمی deploy شده؛ باید آخرین commit را push و دوباره deploy کنی.

---

## ارور: `httpx.ProxyError: 403 Forbidden` یا مشکل شبکه

اگر پشت پروکسی شرکتی هستی، ممکن است لازم باشد پروکسی را برای این ربات غیرفعال کنی:

```bash
export NO_PROXY="*"
export no_proxy="*"
python bot.py
```

یا در محیطی که پروکسی ندارد (مثلاً شبکه شخصی) اجرا کن.

---

## تشخیص سریع

این دو تا را بزن و اگر ارور داد، همان ارور = راهنمای فیکس:

```bash
cd /Users/hamidrezazebardast/topping-bot
source venv/bin/activate
python bot.py
```

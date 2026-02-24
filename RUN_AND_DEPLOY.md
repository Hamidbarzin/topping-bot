# Run locally and deploy (Render / Railway)

## Run locally

1. **Clone and enter project**
   ```bash
   cd topping-bot
   ```

2. **Create virtualenv and install**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Copy `.env.example` to `.env`
   - Set at least:
     - `BOT_TOKEN` — from @BotFather
     - `HAMID_ID` — your Telegram user ID (e.g. get via @userinfobot or bot’s `/id`)
   - Optional: `AMIR_ID`, `MOTAB_ID` for IT and Marketing managers (if unset, those tickets go to Hamid)

4. **Start the bot**
   ```bash
   python bot.py
   ```
   You should see logs like: `Starting polling (drop_pending_updates=True).`

---

## Set env vars (general)

- **Local:** Put variables in `.env` in the project root (bot loads them via `python-dotenv` if installed).
- **Render / Railway / Heroku:** Set in the dashboard under **Environment** (or **Variables**). Do **not** commit `.env` (it should be in `.gitignore`).

Required:

| Variable   | Description |
|-----------|-------------|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `HAMID_ID`  | Telegram user ID of CEO (receives all tickets) |

Optional (bot starts without them but logs a warning; tickets for that department go to Hamid):

| Variable   | Description |
|-----------|-------------|
| `AMIR_ID`  | IT manager user ID |
| `MOTAB_ID` | Marketing manager user ID |

---

## Deploy on Render

1. New **Background Worker** (or **Web Service** if you add a health HTTP server later).
2. Connect repo; build command: `pip install -r requirements.txt` (or leave default).
3. Start command: `python bot.py`.
4. In **Environment**, add:
   - `BOT_TOKEN`
   - `HAMID_ID`
   - `AMIR_ID`, `MOTAB_ID` (optional).
5. Deploy. The bot runs long‑running polling; Render keeps the worker alive. Ensure the plan allows always-on or long-running processes.

---

## Deploy on Railway

1. **New project** → deploy from GitHub/repo.
2. **Variables** tab: add `BOT_TOKEN`, `HAMID_ID`, and optionally `AMIR_ID`, `MOTAB_ID`.
3. **Settings**: set start command to `python bot.py` if not auto-detected.
4. Deploy. Railway runs the process continuously; polling works as-is.

---

## Notes

- **Webhook:** The bot clears any existing webhook on startup so polling works. For webhook deployment (e.g. serverless), you’d switch to `run_webhook()` and set the webhook URL; not included in this setup.
- **Storage:** Tickets are stored in `tickets.json` in the working directory. On Render/Railway, the filesystem may be ephemeral; for production persistence consider a database or external storage and adapt the storage layer in `bot.py`.
- **Only Hamid** can change manager IDs in practice by changing ENV and redeploying; there is no in-chat command to change IDs (by design).

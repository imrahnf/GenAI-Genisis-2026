"""
Mini banking demo app: SQLite + Flask.
- GET / : list accounts and recent transactions
- POST /api/accounts : create account (name, initial_balance)
- POST /api/transfer : transfer between accounts (from_id, to_id, amount)
- GET /api/health : health check

Env:
- APP_TITLE: overrides page <title> and H1 so Config (JSON env) is visible.
- BANK_CURRENCY: label for balances (e.g. \"USD\", \"CAD\").
"""
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_PATH = Path("/data/bank.db")


@app.template_filter("printf")
def _printf(s, value):
    """Jinja filter: '%.2f'|printf(balance) for number formatting."""
    try:
        return s % value
    except (TypeError, ValueError):
        return str(value)


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, balance REAL NOT NULL DEFAULT 0)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, from_account_id INTEGER, to_account_id INTEGER, amount REAL NOT NULL, created_at DEFAULT CURRENT_TIMESTAMP)"
        )


@app.route("/")
def index():
    with get_db() as conn:
        accounts = conn.execute("SELECT id, name, balance FROM accounts ORDER BY id").fetchall()
        txns = conn.execute(
            "SELECT t.id, t.amount, t.created_at, a1.name AS from_name, a2.name AS to_name FROM transactions t "
            "LEFT JOIN accounts a1 ON t.from_account_id = a1.id LEFT JOIN accounts a2 ON t.to_account_id = a2.id "
            "ORDER BY t.id DESC LIMIT 50"
        ).fetchall()
    accounts_list = [{"id": r["id"], "name": r["name"], "balance": r["balance"]} for r in accounts]
    txns_list = [
        {"id": r["id"], "from": r["from_name"], "to": r["to_name"], "amount": r["amount"], "created_at": r["created_at"]}
        for r in txns
    ]
    title = os.environ.get("APP_TITLE", "Bank Demo")
    currency = os.environ.get("BANK_CURRENCY", "")
    return render_template_string(
        """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <script>
    tailwind.config = { theme: { extend: { fontFamily: { sans: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'] } } } };
  </script>
</head>
<body class="bg-stone-50 font-sans text-stone-900 antialiased min-h-screen">
  <div class="max-w-2xl mx-auto px-4 py-8">
    <h1 class="text-xl font-semibold tracking-tight text-stone-900 mb-6">{{ title }}</h1>

    <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm mb-6">
      <h2 class="text-sm font-semibold text-stone-900 mb-3">New account</h2>
      <form id="create-account-form" class="flex flex-wrap gap-3 items-end">
        <div class="flex-1 min-w-[120px]">
          <label for="acct-name" class="block text-xs font-medium text-stone-500 mb-1">Name</label>
          <input type="text" id="acct-name" placeholder="Account name" required class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <div class="min-w-[100px]">
          <label for="acct-balance" class="block text-xs font-medium text-stone-500 mb-1">Initial balance</label>
          <input type="number" id="acct-balance" placeholder="0" step="0.01" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <button type="submit" class="rounded-full bg-stone-900 text-white text-sm font-medium px-4 py-2 shadow-sm hover:bg-stone-800 active:scale-[0.98] transition">Create</button>
        <span id="acct-msg" class="text-xs text-stone-500 self-center"></span>
      </form>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white shadow-sm overflow-hidden mb-6">
      <div class="px-5 py-4 border-b border-stone-100">
        <h2 class="text-sm font-semibold text-stone-900">Accounts</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-stone-100">
              <th class="text-left py-3 px-4 font-medium text-stone-500">ID</th>
              <th class="text-left py-3 px-4 font-medium text-stone-500">Name</th>
              <th class="text-right py-3 px-4 font-medium text-stone-500">Balance {{ currency }}</th>
            </tr>
          </thead>
          <tbody>
            {% for a in accounts %}
            <tr class="border-b border-stone-100">
              <td class="py-3 px-4 text-stone-600">{{ a.id }}</td>
              <td class="py-3 px-4 text-stone-900">{{ a.name }}</td>
              <td class="py-3 px-4 text-right font-medium text-stone-900">{{ "%.2f"|printf(a.balance) }}</td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="py-8 px-4 text-center text-stone-500">No accounts yet.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm mb-6">
      <h2 class="text-sm font-semibold text-stone-900 mb-3">Transfer</h2>
      <form id="transfer-form" class="flex flex-wrap gap-3 items-end">
        <div class="min-w-[70px]">
          <label for="from-id" class="block text-xs font-medium text-stone-500 mb-1">From ID</label>
          <input type="number" id="from-id" placeholder="From" min="1" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <div class="min-w-[70px]">
          <label for="to-id" class="block text-xs font-medium text-stone-500 mb-1">To ID</label>
          <input type="number" id="to-id" placeholder="To" min="1" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <div class="min-w-[90px]">
          <label for="amount" class="block text-xs font-medium text-stone-500 mb-1">Amount</label>
          <input type="number" id="amount" placeholder="0" step="0.01" min="0.01" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <button type="submit" class="rounded-full bg-stone-900 text-white text-sm font-medium px-4 py-2 shadow-sm hover:bg-stone-800 active:scale-[0.98] transition">Send</button>
        <span id="tx-msg" class="text-xs text-stone-500 self-center"></span>
      </form>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white shadow-sm overflow-hidden">
      <div class="px-5 py-4 border-b border-stone-100">
        <h2 class="text-sm font-semibold text-stone-900">Recent Transactions</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-stone-100">
              <th class="text-left py-3 px-4 font-medium text-stone-500">From</th>
              <th class="text-left py-3 px-4 font-medium text-stone-500">To</th>
              <th class="text-right py-3 px-4 font-medium text-stone-500">Amount</th>
              <th class="text-left py-3 px-4 font-medium text-stone-500">Time</th>
            </tr>
          </thead>
          <tbody>
            {% for t in txns %}
            <tr class="border-b border-stone-100">
              <td class="py-3 px-4 text-stone-900">{{ t.from or '—' }}</td>
              <td class="py-3 px-4 text-stone-900">{{ t.to or '—' }}</td>
              <td class="py-3 px-4 text-right font-medium text-stone-900">{{ "%.2f"|printf(t.amount) }}</td>
              <td class="py-3 px-4 text-stone-600">{{ t.created_at }}</td>
            </tr>
            {% else %}
            <tr><td colspan="4" class="py-8 px-4 text-center text-stone-500">No transactions yet.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <script>
    document.getElementById('create-account-form').onsubmit = async function (e) {
      e.preventDefault();
      var name = (document.getElementById('acct-name').value || '').trim();
      var balStr = document.getElementById('acct-balance').value || '0';
      var msg = document.getElementById('acct-msg');
      if (!name) { msg.textContent = 'Name required.'; return; }
      msg.textContent = 'Creating...';
      try {
        var r = await fetch('/api/accounts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, initial_balance: parseFloat(balStr) || 0 })
        });
        var data = await r.json();
        if (!data.ok) { msg.textContent = data.error || 'Error'; return; }
        location.reload();
      } catch (e) {
        msg.textContent = 'Error creating account.';
      }
    };
    document.getElementById('transfer-form').onsubmit = async function (e) {
      e.preventDefault();
      var fromId = parseInt(document.getElementById('from-id').value || '0', 10);
      var toId = parseInt(document.getElementById('to-id').value || '0', 10);
      var amt = parseFloat(document.getElementById('amount').value || '0');
      var msg = document.getElementById('tx-msg');
      if (!fromId || !toId || !amt) { msg.textContent = 'All fields required.'; return; }
      msg.textContent = 'Transferring...';
      try {
        var r = await fetch('/api/transfer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ from_id: fromId, to_id: toId, amount: amt })
        });
        var data = await r.json();
        if (!data.ok) { msg.textContent = data.error || 'Error'; return; }
        location.reload();
      } catch (e) {
        msg.textContent = 'Error transferring.';
      }
    };
    setInterval(function () { location.reload(); }, 4000);
  </script>
</body>
</html>
""",
        title=title,
        currency=currency,
        accounts=accounts_list,
        txns=txns_list,
    )


@app.route("/api/accounts", methods=["POST"])
def create_account():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()[:200]
    balance = float(data.get("initial_balance", 0))
    if not name:
        return jsonify({"ok": False, "error": "missing name"}), 400
    with get_db() as conn:
        cur = conn.execute("INSERT INTO accounts (name, balance) VALUES (?, ?)", (name, balance))
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})


@app.route("/api/seed", methods=["POST"])
def seed_accounts():
    """Seed the database with a number of demo accounts in a single call."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        count = int(data.get("count", 0))
    except (TypeError, ValueError):
        count = 0
    if count <= 0 or count > 1000:
        return jsonify({"ok": False, "error": "count must be between 1 and 1000"}), 400
    initial_balance = float(data.get("initial_balance", 100))
    prefix = (data.get("name_prefix") or "User")[:50]
    with get_db() as conn:
        for i in range(1, count + 1):
            name = f"{prefix}{i}"
            conn.execute("INSERT INTO accounts (name, balance) VALUES (?, ?)", (name, initial_balance))
        conn.commit()
    return jsonify({"ok": True, "seeded": count})


@app.route("/api/transfer", methods=["POST"])
def transfer():
    data = request.get_json(force=True, silent=True) or {}
    from_id = int(data.get("from_id", 0))
    to_id = int(data.get("to_id", 0))
    amount = float(data.get("amount", 0))
    if from_id <= 0 or to_id <= 0 or amount <= 0:
        return jsonify({"ok": False, "error": "invalid from_id, to_id, or amount"}), 400
    with get_db() as conn:
        row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,)).fetchone()
        if not row or row["balance"] < amount:
            return jsonify({"ok": False, "error": "insufficient balance"}), 400
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
        conn.execute("INSERT INTO transactions (from_account_id, to_account_id, amount) VALUES (?, ?, ?)", (from_id, to_id, amount))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    return jsonify({"status": "running"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8501, debug=False)

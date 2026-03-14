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
<html>
<head><meta charset="utf-8"><title>{{ title }}</title>
<style>
  body { font-family: system-ui; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.5rem; }
  table { width: 100%%; border-collapse: collapse; margin: 1rem 0; }
  th, td { text-align: left; padding: 0.4rem; border-bottom: 1px solid #eee; }
  form { margin: 0.5rem 0; display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
  input[type=text], input[type=number] { padding: 0.35rem 0.5rem; font: inherit; }
  button { padding: 0.4rem 0.8rem; font: inherit; cursor: pointer; background: #333; color: #fff; border: none; border-radius: 4px; }
  button:hover { background: #111; }
  .muted { color: #666; font-size: 0.85rem; }
</style>
</head>
<body>
  <h1>{{ title }}</h1>
  <h2>Accounts</h2>
  <form id="create-account-form">
    <strong>New account:</strong>
    <input type="text" id="acct-name" placeholder="Name" required />
    <input type="number" id="acct-balance" placeholder="Initial balance" step="0.01" />
    <button type="submit">Create</button>
    <span class="muted" id="acct-msg"></span>
  </form>
  <table>
    <tr><th>ID</th><th>Name</th><th>Balance {{ currency }}</th></tr>
    {% for a in accounts %}
    <tr><td>{{ a.id }}</td><td>{{ a.name }}</td><td>{{ a.balance }}</td></tr>
    {% else %}
    <tr><td colspan="3">No accounts yet.</td></tr>
    {% endfor %}
  </table>
  <h2>Recent Transactions</h2>
  <form id="transfer-form">
    <strong>Transfer:</strong>
    <input type="number" id="from-id" placeholder="From ID" />
    <input type="number" id="to-id" placeholder="To ID" />
    <input type="number" id="amount" placeholder="Amount" step="0.01" />
    <button type="submit">Send</button>
    <span class="muted" id="tx-msg"></span>
  </form>
  <table>
    <tr><th>From</th><th>To</th><th>Amount</th><th>Time</th></tr>
    {% for t in txns %}
    <tr><td>{{ t.from }}</td><td>{{ t.to }}</td><td>{{ t.amount }}</td><td>{{ t.created_at }}</td></tr>
    {% else %}
    <tr><td colspan="4">No transactions yet.</td></tr>
    {% endfor %}
  </table>
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

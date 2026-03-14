"""
Mini banking demo app: SQLite + Flask.
- GET / : list accounts and recent transactions
- POST /api/accounts : create account (name, initial_balance)
- POST /api/transfer : transfer between accounts (from_id, to_id, amount)
- GET /api/health : health check
"""
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
    return render_template_string(
        """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bank Demo</title>
<style>
  body { font-family: system-ui; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.5rem; }
  table { width: 100%%; border-collapse: collapse; margin: 1rem 0; }
  th, td { text-align: left; padding: 0.4rem; border-bottom: 1px solid #eee; }
</style>
</head>
<body>
  <h1>Bank Demo</h1>
  <h2>Accounts</h2>
  <table>
    <tr><th>ID</th><th>Name</th><th>Balance</th></tr>
    {% for a in accounts %}
    <tr><td>{{ a.id }}</td><td>{{ a.name }}</td><td>{{ a.balance }}</td></tr>
    {% else %}
    <tr><td colspan="3">No accounts yet.</td></tr>
    {% endfor %}
  </table>
  <h2>Recent Transactions</h2>
  <table>
    <tr><th>From</th><th>To</th><th>Amount</th><th>Time</th></tr>
    {% for t in txns %}
    <tr><td>{{ t.from }}</td><td>{{ t.to }}</td><td>{{ t.amount }}</td><td>{{ t.created_at }}</td></tr>
    {% else %}
    <tr><td colspan="4">No transactions yet.</td></tr>
    {% endfor %}
  </table>
</body>
</html>
""",
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

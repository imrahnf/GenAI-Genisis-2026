"""
Single-user spending tracker with anomaly detection. SQLite + Flask.
- GET / : dashboard (user name, balance, transaction list; rows above threshold in red, anomaly count)
- POST /api/transactions : add transaction (amount, description)
- POST /api/seed : seed N random transactions for demo
- GET /api/health : health check

Env: APP_TITLE, USER_NAME, STARTING_BALANCE, ANOMALY_THRESHOLD, CURRENCY.
"""
import os
import random
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_PATH = Path("/data/spending.db")


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
            "CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL, balance REAL NOT NULL DEFAULT 0)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount REAL NOT NULL, description TEXT NOT NULL DEFAULT '', created_at DEFAULT CURRENT_TIMESTAMP)"
        )


def ensure_user():
    """Create the single user from env if not present."""
    with get_db() as conn:
        row = conn.execute("SELECT id, name, balance FROM user WHERE id = 1").fetchone()
        if row:
            return
        name = os.environ.get("USER_NAME", "Demo User").strip() or "Demo User"
        balance = float(os.environ.get("STARTING_BALANCE", "1000"))
        conn.execute("INSERT INTO user (id, name, balance) VALUES (1, ?, ?)", (name, balance))
        conn.commit()


@app.route("/")
def index():
    ensure_user()
    threshold = float(os.environ.get("ANOMALY_THRESHOLD", "100"))
    title = os.environ.get("APP_TITLE", "Spending & Anomaly Tracker")
    currency = os.environ.get("CURRENCY", "USD")

    with get_db() as conn:
        user = conn.execute("SELECT id, name, balance FROM user WHERE id = 1").fetchone()
        txns = conn.execute(
            "SELECT id, amount, description, created_at FROM transactions WHERE user_id = 1 ORDER BY id DESC LIMIT 100"
        ).fetchall()

    if not user:
        return "No user.", 500

    txns_list = []
    anomaly_count = 0
    for r in txns:
        amount = float(r["amount"])
        is_anomaly = amount > threshold
        if is_anomaly:
            anomaly_count += 1
        txns_list.append({
            "id": r["id"],
            "amount": amount,
            "description": (r["description"] or "").strip(),
            "created_at": r["created_at"],
            "is_anomaly": is_anomaly,
        })

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
      <p class="text-xs font-medium uppercase tracking-wider text-stone-500 mb-1">Account</p>
      <p class="text-lg font-semibold text-stone-900">{{ user_name }}</p>
      <p class="mt-1 text-2xl font-semibold text-stone-800">{{ "%.2f"|printf(balance) }} <span class="text-sm font-normal text-stone-500">{{ currency }}</span></p>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm mb-6">
      <h2 class="text-sm font-semibold text-stone-900 mb-3">Add transaction</h2>
      <form id="add-form" class="flex flex-wrap gap-3 items-end">
        <div class="flex-1 min-w-[100px]">
          <label for="amount" class="block text-xs font-medium text-stone-500 mb-1">Amount</label>
          <input type="number" id="amount" step="0.01" required placeholder="0.00" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <div class="flex-1 min-w-[120px]">
          <label for="description" class="block text-xs font-medium text-stone-500 mb-1">Description</label>
          <input type="text" id="description" placeholder="e.g. Coffee" class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <button type="submit" class="rounded-full bg-stone-900 text-white text-sm font-medium px-4 py-2 shadow-sm hover:bg-stone-800 active:scale-[0.98] transition">Add</button>
        <span id="add-msg" class="text-xs text-stone-500 self-center"></span>
      </form>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white shadow-sm overflow-hidden">
      <div class="px-5 py-4 border-b border-stone-100 flex items-center justify-between flex-wrap gap-2">
        <h2 class="text-sm font-semibold text-stone-900">Transactions</h2>
        <p class="text-xs text-stone-500">Anomalies: <span class="font-medium text-stone-700">{{ anomaly_count }}</span> (amount &gt; {{ "%.0f"|printf(threshold) }} {{ currency }})</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-stone-100">
              <th class="text-left py-3 px-4 font-medium text-stone-500">Date</th>
              <th class="text-left py-3 px-4 font-medium text-stone-500">Description</th>
              <th class="text-right py-3 px-4 font-medium text-stone-500">Amount</th>
              <th class="w-20 py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {% for t in txns %}
            <tr class="border-b border-stone-100 {{ 'bg-rose-50/50' if t.is_anomaly else '' }}">
              <td class="py-3 px-4 text-stone-600">{{ t.created_at }}</td>
              <td class="py-3 px-4 text-stone-900">{{ t.description or '—' }}</td>
              <td class="py-3 px-4 text-right font-medium {{ 'text-rose-600' if t.is_anomaly else 'text-stone-900' }}">{{ "%.2f"|printf(t.amount) }} {{ currency }}</td>
              <td class="py-3 px-4">{% if t.is_anomaly %}<span class="inline-block rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium text-rose-700">Anomaly</span>{% endif %}</td>
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
    document.getElementById('add-form').onsubmit = async function (e) {
      e.preventDefault();
      var amount = parseFloat(document.getElementById('amount').value);
      var desc = (document.getElementById('description').value || '').trim();
      var msg = document.getElementById('add-msg');
      if (isNaN(amount)) { msg.textContent = 'Enter amount.'; return; }
      msg.textContent = 'Adding...';
      try {
        var r = await fetch('/api/transactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: amount, description: desc || 'Purchase' })
        });
        var data = await r.json();
        if (!data.ok) { msg.textContent = data.error || 'Error'; return; }
        location.reload();
      } catch (e) {
        msg.textContent = 'Request failed.';
      }
    };
    setInterval(function () { location.reload(); }, 4000);
  </script>
</body>
</html>
""",
        title=title,
        currency=currency,
        user_name=user["name"],
        balance=float(user["balance"]),
        threshold=threshold,
        txns=txns_list,
        anomaly_count=anomaly_count,
    )


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    ensure_user()
    data = request.get_json(force=True, silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    description = (data.get("description") or "Purchase").strip()[:500]

    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be positive"}), 400

    with get_db() as conn:
        row = conn.execute("SELECT balance FROM user WHERE id = 1").fetchone()
        if not row:
            return jsonify({"ok": False, "error": "user not found"}), 500
        balance = float(row["balance"])
        if balance < amount:
            return jsonify({"ok": False, "error": "insufficient balance"}), 400
        conn.execute(
            "INSERT INTO transactions (user_id, amount, description) VALUES (1, ?, ?)",
            (amount, description),
        )
        conn.execute("UPDATE user SET balance = balance - ? WHERE id = 1", (amount,))
        conn.commit()
        cur = conn.execute("SELECT last_insert_rowid() AS id")
        txn_id = cur.fetchone()["id"]
    return jsonify({"ok": True, "id": txn_id})


@app.route("/api/seed", methods=["POST"])
def seed():
    """Seed transactions: use 'amount' for a single transaction of that size (e.g. 1), or 'count' + 'max_amount' for N random ones."""
    ensure_user()
    data = request.get_json(force=True, silent=True) or {}

    # Single transaction of fixed amount (e.g. 1 for "seed with 1$")
    if "amount" in data:
        try:
            single_amount = float(data["amount"])
        except (TypeError, ValueError):
            single_amount = 1.0
        if single_amount <= 0:
            return jsonify({"ok": False, "error": "amount must be positive"}), 400
        desc = (data.get("description") or "Seed").strip()[:200] or "Seed"
        with get_db() as conn:
            row = conn.execute("SELECT balance FROM user WHERE id = 1").fetchone()
            if not row:
                return jsonify({"ok": False, "error": "user not found"}), 500
            if float(row["balance"]) < single_amount:
                return jsonify({"ok": False, "error": "insufficient balance"}), 400
            conn.execute(
                "INSERT INTO transactions (user_id, amount, description) VALUES (1, ?, ?)",
                (single_amount, desc),
            )
            conn.execute("UPDATE user SET balance = balance - ? WHERE id = 1", (single_amount,))
            conn.commit()
        return jsonify({"ok": True, "seeded": 1})

    try:
        count = int(data.get("count", 10))
    except (TypeError, ValueError):
        count = 10
    if count <= 0 or count > 500:
        return jsonify({"ok": False, "error": "count must be between 1 and 500"}), 400
    try:
        max_amount = float(data.get("max_amount", 200))
    except (TypeError, ValueError):
        max_amount = 200
    if max_amount <= 0:
        max_amount = 200

    with get_db() as conn:
        row = conn.execute("SELECT balance FROM user WHERE id = 1").fetchone()
        if not row:
            return jsonify({"ok": False, "error": "user not found"}), 500
        descriptions = ["Coffee", "Lunch", "Groceries", "Subscription", "Transfer", "Payment", "Refund", "Other"]
        for _ in range(count):
            amount = round(random.uniform(1, max_amount), 2)
            desc = random.choice(descriptions)
            conn.execute(
                "INSERT INTO transactions (user_id, amount, description) VALUES (1, ?, ?)",
                (amount, desc),
            )
            conn.execute("UPDATE user SET balance = balance - ? WHERE id = 1", (amount,))
        conn.commit()

    return jsonify({"ok": True, "seeded": count})


@app.route("/api/health")
def health():
    return jsonify({"status": "running"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8501, debug=False)

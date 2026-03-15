"""
Favorite foods demo app: SQLite + Flask.
- GET / : simple UI listing foods + form to add
- POST /add : body {"food": "string"} -> insert row, return {"ok": true}

Env:
- APP_TITLE: overrides page <title> and H1 so Config (JSON env) is visible.
"""
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_PATH = Path("/data/foods.db")


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS foods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at DEFAULT CURRENT_TIMESTAMP)"
        )


@app.route("/")
def index():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM foods ORDER BY id DESC").fetchall()
    foods = [{"id": r["id"], "name": r["name"], "created_at": r["created_at"]} for r in rows]
    title = os.environ.get("APP_TITLE", "Favorite Foods")
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
      <h2 class="text-sm font-semibold text-stone-900 mb-3">Add food</h2>
      <form id="add-form" class="flex flex-wrap gap-3 items-end">
        <div class="flex-1 min-w-[140px]">
          <label for="food-input" class="block text-xs font-medium text-stone-500 mb-1">Food name</label>
          <input type="text" name="food" id="food-input" placeholder="e.g. Pizza" required class="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:bg-white focus:ring-2 focus:ring-stone-900/10 focus:outline-none" />
        </div>
        <button type="submit" class="rounded-full bg-stone-900 text-white text-sm font-medium px-4 py-2 shadow-sm hover:bg-stone-800 active:scale-[0.98] transition">Add</button>
        <span id="add-msg" class="text-xs text-stone-500 self-center"></span>
      </form>
    </div>

    <div class="rounded-2xl border border-stone-200 bg-white shadow-sm overflow-hidden">
      <div class="px-5 py-4 border-b border-stone-100">
        <h2 class="text-sm font-semibold text-stone-900">Foods</h2>
      </div>
      <ul id="food-list" class="divide-y divide-stone-100">
        {% for f in foods %}
        <li class="py-3 px-5 text-sm text-stone-900 flex justify-between items-center">
          <span>{{ f.name }}</span>
          <span class="text-xs text-stone-500">{{ f.created_at }}</span>
        </li>
        {% else %}
        <li id="empty-msg" class="py-8 px-5 text-center text-stone-500 text-sm">No foods yet. Add one or let the agent add some.</li>
        {% endfor %}
      </ul>
    </div>
  </div>
  <script>
    document.getElementById('add-form').onsubmit = async function(e) {
      e.preventDefault();
      var input = document.getElementById('food-input');
      var name = (input && input.value || '').trim();
      if (!name) return;
      var btn = this.querySelector('button[type=submit]');
      if (btn) btn.disabled = true;
      try {
        var r = await fetch('/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ food: name })
        });
        var data = await r.json();
        if (data.ok) {
          var empty = document.getElementById('empty-msg');
          if (empty) empty.remove();
          var ul = document.getElementById('food-list');
          var li = document.createElement('li');
          li.className = 'py-3 px-5 text-sm text-stone-900 flex justify-between items-center';
          li.innerHTML = '<span>' + name + '</span><span class="text-xs text-stone-500">' + new Date().toLocaleString() + '</span>';
          ul.insertBefore(li, ul.firstChild);
          input.value = '';
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    };
    setInterval(function () { location.reload(); }, 4000);
  </script>
</body>
</html>
""",
        title=title,
        foods=foods,
    )


@app.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True, silent=True) or {}
    food = (data.get("food") or request.form.get("food") or "").strip()
    if not food:
        return jsonify({"ok": False, "error": "missing food"}), 400
    with get_db() as conn:
        conn.execute("INSERT INTO foods (name) VALUES (?)", (food[:200],))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    return jsonify({"status": "running"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8501, debug=False)

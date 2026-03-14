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
<html>
<head><meta charset="utf-8"><title>{{ title }}</title>
<style>
  body { font-family: system-ui; max-width: 480px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.5rem; }
  ul { list-style: none; padding: 0; }
  li { padding: 0.4rem 0; border-bottom: 1px solid #eee; }
  form { display: flex; gap: 0.5rem; margin-top: 1rem; }
  input[type=text] { flex: 1; padding: 0.5rem; }
  button { padding: 0.5rem 1rem; background: #333; color: #fff; border: none; cursor: pointer; }
</style>
</head>
<body>
  <h1>{{ title }}</h1>
  <ul id="food-list">
    {% for f in foods %}
    <li>{{ f.name }} <small>{{ f.created_at }}</small></li>
    {% else %}
    <li id="empty-msg"><em>No foods yet. Add one or let the agent add some.</em></li>
    {% endfor %}
  </ul>
  <form id="add-form">
    <input type="text" name="food" id="food-input" placeholder="Food name" required />
    <button type="submit">Add</button>
  </form>
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
          li.textContent = name + ' ';
          var small = document.createElement('small');
          small.textContent = new Date().toLocaleString();
          li.appendChild(small);
          ul.insertBefore(li, ul.firstChild);
          input.value = '';
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    };
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

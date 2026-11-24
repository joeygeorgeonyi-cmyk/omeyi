import os
import sqlite3
from datetime import datetime, timedelta, date
from flask import Flask, request, redirect, session, render_template_string, jsonify, send_file
import io

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except:
    HAS_PG = False

app = Flask(__name__)
app.secret_key = "omeyi-secret-v12"
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL and HAS_PG)

def db():
    if USE_PG:
        c = psycopg2.connect(DATABASE_URL)
        c.autocommit = True
        return c
    c = sqlite3.connect("omeyi.db")
    c.row_factory = sqlite3.Row
    return c

def q(sql, args=(), commit=False):
    conn = db()
    try:
        if USE_PG:
            sql = sql.replace("?", "%s")
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, args)
            if sql.strip().upper().startswith("SELECT"):
                return [dict(r) for r in cur.fetchall()]
            if commit:
                return True
            return []
        else:
            cur = conn.cursor()
            cur.execute(sql, args)
            if sql.strip().upper().startswith("SELECT"):
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            if commit:
                conn.commit()
            return []
    finally:
        conn.close()

def init_db():
    if USE_PG:
        q("CREATE TABLE IF NOT EXISTS shops (id SERIAL PRIMARY KEY, name TEXT UNIQUE)", commit=True)
        q("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, shop_id INTEGER, name TEXT, role TEXT, pin TEXT)", commit=True)
        q("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, shop_id INTEGER, item TEXT, amount REAL, qty INTEGER, seller TEXT, date TEXT)", commit=True)
        q("CREATE TABLE IF NOT EXISTS reports (id SERIAL PRIMARY KEY, shop_id INTEGER, date TEXT, opening REAL, closing REAL, sales REAL, purchases REAL, expenditure REAL, profit REAL, bad_debt REAL, debtors REAL)", commit=True)
    else:
        q("CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)", commit=True)
        q("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, name TEXT, role TEXT, pin TEXT)", commit=True)
        q("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, item TEXT, amount REAL, qty INTEGER, seller TEXT, date TEXT)", commit=True)
        q("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER, date TEXT, opening REAL, closing REAL, sales REAL, purchases REAL, expenditure REAL, profit REAL, bad_debt REAL, debtors REAL)", commit=True)
    shops = q("SELECT * FROM shops")
    if not shops:
        q("INSERT INTO shops (name) VALUES (?)", ("Omeyi Shop",), commit=True)
        shops = q("SELECT * FROM shops")
    shop = shops[0]
    sid = shop["id"]
    users = q("SELECT * FROM users WHERE shop_id=?", (sid,))
    if not users:
        for nm, rl in [("Super Admin", "superadmin"), ("MD / CEO", "md"), ("Manager", "manager"), ("Salesperson", "sales")]:
            q("INSERT INTO users (shop_id,name,role,pin) VALUES (?,?,?,?)", (sid, nm, rl, "1234"), commit=True)

init_db()

BASE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial;background:#f3f6fb;margin:0;padding:14px}
.card{background:#fff;border-radius:14px;padding:16px;box-shadow:0 4px 14px rgba(0,0,0,.08);max-width:520px;margin:0 auto}
h2{margin:0 0 10px} h3{margin:14px 0 6px}
input,select,button{width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:10px;font-size:16px;box-sizing:border-box}
button{background:#0b6efd;color:#fff;border:0;font-weight:700}
a.btn{display:block;text-align:center;background:#eef3ff;padding:12px;margin:6px 0;border-radius:10px;text-decoration:none;color:#0b6efd;font-weight:700}
a.btn.red{background:#ffecec;color:#c00} a.btn.green{background:#e7f8ec;color:#0a7a2e}
.small{color:#666;font-size:13px} .big{font-size:28px;font-weight:800}
.row{display:flex;gap:8px} .row>*{flex:1}
table{width:100%;border-collapse:collapse;font-size:14px} td,th{border-bottom:1px solid #eee;padding:8px;text-align:left}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;background:#eef3ff;font-size:12px}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
</style></head><body><div class="card">{{BODY}}</div></body></html>
"""
def page(body):
    return render_template_string(BASE.replace("{{BODY}}", body))

def today_str():
    return date.today().isoformat()

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    u = q("SELECT * FROM users WHERE id=?", (uid,))
    return u[0] if u else None

def current_shop():
    s = q("SELECT * FROM shops")
    return s[0] if s else None

def require_login():
    if not current_user():
        return redirect("/login")
    return None

@app.before_request
def auto_shop():
    if request.path in ("/login", "/health", "/"):
        return
    if not current_shop():
        init_db()

@app.route("/health")
def health():
    return jsonify({"ok": True, "pg": USE_PG})

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        shop = current_shop()
        if not shop:
            init_db()
            shop = current_shop()
        u = q("SELECT * FROM users WHERE shop_id=? AND role=?", (shop["id"], role))
        if not u:
            return page("<h2>Omeyi Shop</h2><p style='color:red'>User not found. Tell admin to reset users.</p><a class='btn' href='/login'>Back</a>")
        session["uid"] = u[0]["id"]
        session["role"] = role
        return redirect("/dashboard")
    return page("""
    <h2>Omeyi Shop</h2><p class="small">Smart Multi-Shop Daily Ledger — V12.1</p>
    <p>Press who you be:</p>
    <form method="post">
    <input type="hidden" name="role" value="superadmin"><button>Enter as Super Admin</button></form>
    <form method="post">
    <input type="hidden" name="role" value="md"><button>Enter as MD / CEO</button></form>
    <form method="post">
    <input type="hidden" name="role" value="manager"><button>Enter as Manager</button></form>
    <form method="post">
    <input type="hidden" name="role" value="sales"><button>Enter as Salesperson</button></form>
    <p class="small">All roles use PIN 1234 inside. No password wahala.</p>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard")
def dashboard():
    r = require_login()
    if r:
        return r
    u = current_user()
    shop = current_shop()
    t = today_str()
    sales = q("SELECT * FROM sales WHERE shop_id=? AND date=?", (shop["id"], t))
    total = sum(float(s["amount"] or 0) for s in sales)
    reps = q("SELECT * FROM reports WHERE shop_id=? AND date=?", (shop["id"], t))
    rep = reps[0] if reps else None
    opening = rep["opening"] if rep else 0
    return page(f"""
    <div class="top"><div><h2>Omeyi Shop</h2><span class="badge">{u['name']} • {u['role']}</span></div><a href='/logout'>Logout</a></div>
    <p class="small">Today: {t} • Opening: ₦{opening:,.0f}</p>
    <div class="big">₦{total:,.0f}</div><p class="small">Today Sales</p>
    <a class="btn green" href="/add-sale">+ Add Sale</a>
    <a class="btn" href="/sales">View Sales Today</a>
    <a class="btn" href="/daily-report">Daily Report (Opening / Closing)</a>
    <a class="btn" href="/history">History (Last 14 Days)</a>
    <a class="btn" href="/export-csv">Download CSV</a>
    <a class="btn" href="/backup">Download Backup (JSON)</a>
    <a class="btn red" href="/reset-today">Reset Today Sales</a>
    <p class="small">PIN for all: 1234 • Live on Render + Postgres</p>
    """)

@app.route("/add-sale", methods=["GET", "POST"])
def add_sale():
    r = require_login()
    if r:
        return r
    u = current_user()
    shop = current_shop()
    if request.method == "POST":
        item = request.form.get("item", "").strip() or "Item"
        try:
            amount = float(request.form.get("amount", "0") or 0)
        except:
            amount = 0
        try:
            qty = int(request.form.get("qty", "1") or 1)
        except:
            qty = 1
        q("INSERT INTO sales (shop_id,item,amount,qty,seller,date) VALUES (?,?,?,?,?,?)", (shop["id"], item, amount, qty, u["name"], today_str()), commit=True)
        return redirect("/dashboard")
    return page("""
    <h2>Add Sale</h2>
    <form method="post">
    <input name="item" placeholder="Item name e.g. Rice 50kg" required>
    <input name="amount" type="number" step="0.01" placeholder="Amount ₦" required>
    <input name="qty" type="number" value="1" placeholder="Qty">
    <button>Save Sale</button></form>
    <a class="btn" href="/dashboard">Back</a>
    """)

@app.route("/sales")
def sales_list():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    rows = q("SELECT * FROM sales WHERE shop_id=? AND date=? ORDER BY id DESC", (shop["id"], today_str()))
    html = "<h2>Sales Today</h2><table><tr><th>Item</th><th>Amount</th><th>Qty</th></tr>"
    for s in rows:
        html += f"<tr><td>{s['item']}</td><td>₦{float(s['amount'] or 0):,.0f}</td><td>{s['qty']}</td></tr>"
    html += "</table><a class='btn' href='/dashboard'>Back</a>"
    return page(html)

@app.route("/daily-report", methods=["GET", "POST"])
def daily_report():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    t = today_str()
    if request.method == "POST":
        def f(n):
            try:
                return float(request.form.get(n, "0") or 0)
            except:
                return 0
        opening = f("opening"); closing = f("closing"); purchases = f("purchases"); expenditure = f("expenditure"); bad_debt = f("bad_debt"); debtors = f("debtors")
        sales = q("SELECT * FROM sales WHERE shop_id=? AND date=?", (shop["id"], t))
        stotal = sum(float(s["amount"] or 0) for s in sales)
        profit = (closing - opening) + stotal - purchases - expenditure - bad_debt
        ex = q("SELECT * FROM reports WHERE shop_id=? AND date=?", (shop["id"], t))
        if ex:
            q("UPDATE reports SET opening=?, closing=?, sales=?, purchases=?, expenditure=?, profit=?, bad_debt=?, debtors=? WHERE id=?", (opening, closing, stotal, purchases, expenditure, profit, bad_debt, debtors, ex[0]["id"]), commit=True)
        else:
            q("INSERT INTO reports (shop_id,date,opening,closing,sales,purchases,expenditure,profit,bad_debt,debtors) VALUES (?,?,?,?,?,?,?,?,?,?)", (shop["id"], t, opening, closing, stotal, purchases, expenditure, profit, bad_debt, debtors), commit=True)
        return redirect("/dashboard")
    reps = q("SELECT * FROM reports WHERE shop_id=? AND date=?", (shop["id"], t))
    rep = reps[0] if reps else {}
    def v(k):
        return rep.get(k, 0) if rep else 0
    return page(f"""
    <h2>Daily Report — {t}</h2>
    <form method="post">
    Opening ₦ <input name="opening" type="number" step="0.01" value="{v('opening')}">
    Closing ₦ <input name="closing" type="number" step="0.01" value="{v('closing')}">
    Purchases ₦ <input name="purchases" type="number" step="0.01" value="{v('purchases')}">
    Expenditure ₦ <input name="expenditure" type="number" step="0.01" value="{v('expenditure')}">
    Bad Debt ₦ <input name="bad_debt" type="number" step="0.01" value="{v('bad_debt')}">
    Debtors ₦ <input name="debtors" type="number" step="0.01" value="{v('debtors')}">
    <button>Save Report</button></form>
    <a class="btn" href="/dashboard">Back</a>
    """)

@app.route("/history")
def history():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    start = (date.today() - timedelta(days=13)).isoformat()
    reps = q("SELECT * FROM reports WHERE shop_id=? AND date>=? ORDER BY date DESC", (shop["id"], start))
    html = "<h2>History — Last 14 Days</h2><table><tr><th>Date</th><th>Sales</th><th>Profit</th></tr>"
    for x in reps:
        html += f"<tr><td>{x['date']}</td><td>₦{float(x['sales'] or 0):,.0f}</td><td>₦{float(x['profit'] or 0):,.0f}</td></tr>"
    html += "</table><a class='btn' href='/dashboard'>Back</a>"
    return page(html)

@app.route("/export-csv")
def export_csv():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    rows = q("SELECT * FROM sales WHERE shop_id=? ORDER BY date DESC, id DESC", (shop["id"],))
    out = io.StringIO()
    out.write("date,item,amount,qty,seller\n")
    for s in rows:
        out.write(f"{s['date']},{s['item']},{s['amount']},{s['qty']},{s['seller']}\n")
    return app.response_class(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=omeyi-sales.csv"})

@app.route("/backup")
def backup():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    data = {"shop": shop, "sales": q("SELECT * FROM sales WHERE shop_id=?", (shop["id"],)), "reports": q("SELECT * FROM reports WHERE shop_id=?", (shop["id"],)), "users": q("SELECT * FROM users WHERE shop_id=?", (shop["id"],))}
    return jsonify(data)

@app.route("/reset-today", methods=["GET", "POST"])
def reset_today():
    r = require_login()
    if r:
        return r
    shop = current_shop()
    if request.method == "POST":
        q("DELETE FROM sales WHERE shop_id=? AND date=?", (shop["id"], today_str()), commit=True)
        q("DELETE FROM reports WHERE shop_id=? AND date=?", (shop["id"], today_str()), commit=True)
        return redirect("/dashboard")
    return page("""
    <h2>Reset Today?</h2><p>This go delete today sales + report only.</p>
    <form method="post"><button style="background:#c00">Yes, Reset Today</button></form>
    <a class="btn" href="/dashboard">Cancel</a>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

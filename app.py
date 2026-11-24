import os
import sqlite3
from datetime import date
from flask import Flask, request, redirect, session, g

app = Flask(__name__)
app.secret_key = "omeyi-v12-safe"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

def get_db():
    if "db" not in g:
        if USE_PG:
            import psycopg2
            import psycopg2.extras
            g.db = psycopg2.connect(DATABASE_URL, sslmode="require")
            g.db.autocommit = True
            g.is_pg = True
        else:
            g.db = sqlite3.connect("omeyi.db")
            g.db.row_factory = sqlite3.Row
            g.is_pg = False
    return g.db

def q(sql, args=(), one=False, commit=False):
    db = get_db()
    is_pg = getattr(g, "is_pg", False)
    if is_pg:
        import psycopg2.extras
        sql = sql.replace("?", "%s")
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, args)
        if sql.strip().upper().startswith("SELECT"):
            r = cur.fetchone() if one else cur.fetchall()
            if one:
                return dict(r) if r else None
            return [dict(x) for x in r] if r else []
        return None
    else:
        cur = db.execute(sql, args)
        if commit:
            db.commit()
        if sql.strip().upper().startswith("SELECT"):
            r = cur.fetchone() if one else cur.fetchall()
            if one:
                return dict(r) if r else None
            return [dict(x) for x in r] if r else []
        return None

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
        shop = q("SELECT * FROM shops WHERE name=?", ("Omeyi Shop",), one=True)
        sid = shop["id"]
        for nm, rl in [("Super Admin", "superadmin"), ("MD / CEO", "md"), ("Manager", "manager"), ("Salesperson", "sales")]:
            q("INSERT INTO users (shop_id,name,role,pin) VALUES (?,?,?,?)", (sid, nm, rl, "1234"), commit=True)

@app.before_request
def _init():
    init_db()

LOGIN_HTML = """
<h2 style="font-family:sans-serif;text-align:center">Omeyi Shop</h2>
<p style="text-align:center">No PIN. Just press who you be:</p>
<div style="max-width:300px;margin:auto;display:flex;flex-direction:column;gap:12px">
  <a href="/enter/superadmin" style="padding:14px;background:#111;color:#fff;text-align:center;text-decoration:none;border-radius:10px">Enter as Superadmin</a>
  <a href="/enter/md" style="padding:14px;background:#0a7a42;color:#fff;text-align:center;text-decoration:none;border-radius:10px">Enter as MD / CEO</a>
  <a href="/enter/manager" style="padding:14px;background:#e67e22;color:#fff;text-align:center;text-decoration:none;border-radius:10px">Enter as Manager</a>
  <a href="/enter/sales" style="padding:14px;background:#2563eb;color:#fff;text-align:center;text-decoration:none;border-radius:10px">Enter as Salesperson</a>
</div>
<p style="text-align:center;color:green">V12.1 - Data dey safe for Postgres</p>
"""

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login")
def login():
    return LOGIN_HTML

@app.route("/enter/<role>")
def enter(role):
    shop = q("SELECT * FROM shops ORDER BY id LIMIT 1", one=True)
    user = q("SELECT * FROM users WHERE shop_id=? AND role=?", (shop["id"], role), one=True)
    if not user:
        return "User not found. <a href='/login'>Login</a>"
    session["user"] = user
    session["shop_id"] = shop["id"]
    session["shop_name"] = shop["name"]
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard")
def dashboard():
    u = session.get("user")
    if not u:
        return redirect("/login")
    shop_name = session.get("shop_name")
    role = u["role"]
    sales = q("SELECT * FROM sales WHERE shop_id=? ORDER BY id DESC LIMIT 20", (session["shop_id"],))
    total = sum(float(s["amount"] or 0) for s in sales)
    rows = ""
    for s in sales:
        rows += "<tr><td>" + str(s["date"]) + "</td><td>" + str(s["item"]) + "</td><td>" + str(s["qty"]) + "</td><td>" + str(s["amount"]) + "</td><td>" + str(s["seller"]) + "</td></tr>"
    add_shop = ""
    if role == "superadmin":
        add_shop = "<h3>Add New Shop</h3><form method='POST' action='/add-shop'><input name='name' placeholder='New shop name' required><button>Add Shop</button></form><p>Shops:</p>"
        shops = q("SELECT * FROM shops")
        for sh in shops:
            add_shop += "• " + str(sh["name"]) + " - <a href='/switch-shop/" + str(sh["id"]) + "'>Open</a><br>"
    report_form = ""
    if role in ("manager", "md"):
        report_form = "<h3>Daily Report - 8 Fields</h3><form method='POST' action='/add-report'>Opening <input name='opening' type='number' step='0.01'><br>Closing <input name='closing' type='number' step='0.01'><br>Sales <input name='sales' type='number' step='0.01'><br>Purchases <input name='purchases' type='number' step='0.01'><br>Expenditure <input name='expenditure' type='number' step='0.01'><br>Profit <input name='profit' type='number' step='0.01'><br>Bad Debt <input name='bad_debt' type='number' step='0.01'><br>Debtors <input name='debtors' type='number' step='0.01'><br><button>Submit Report</button></form>"
    sale_form = ""
    if role in ("sales", "manager"):
        sale_form = "<h3>Add Sale</h3><form method='POST' action='/add-sale'>Item <input name='item' required> Qty <input name='qty' type='number' value='1'> Amount <input name='amount' type='number' step='0.01' required><button>Add Sale</button></form>"
    html = "<div style='font-family:sans-serif;max-width:700px;margin:auto;padding:16px'>"
    html += "<h2>" + str(shop_name) + " - " + str(u["name"]) + " (" + str(role) + ")</h2>"
    html += "<p>Total Sales (last 20): <b>" + str(total) + "</b> | <a href='/logout'>Logout</a></p>"
    html += add_shop + report_form + sale_form
    html += "<h3>Recent Sales</h3><table border='1' cellpadding='6'><tr><th>Date</th><th>Item</th><th>Qty</th><th>Amount</th><th>Seller</th></tr>" + rows + "</table>"
    html += "<p style='color:green'>V12.1 Live - Postgres ON: " + str(USE_PG) + "</p></div>"
    return html

@app.route("/add-shop", methods=["POST"])
def add_shop_route():
    if session.get("user", {}).get("role") != "superadmin":
        return redirect("/login")
    name = request.form.get("name", "").strip()
    if name:
        try:
            q("INSERT INTO shops (name) VALUES (?)", (name,), commit=True)
        except Exception:
            pass
        shop = q("SELECT * FROM shops WHERE name=?", (name,), one=True)
        if shop:
            for nm, rl in [("MD / CEO", "md"), ("Manager", "manager"), ("Salesperson", "sales")]:
                q("INSERT INTO users (shop_id,name,role,pin) VALUES (?,?,?,?)", (shop["id"], nm, rl, "1234"), commit=True)
    return redirect("/dashboard")

@app.route("/switch-shop/<int:sid>")
def switch_shop(sid):
    shop = q("SELECT * FROM shops WHERE id=?", (sid,), one=True)
    if shop:
        session["shop_id"] = shop["id"]
        session["shop_name"] = shop["name"]
        role = session.get("user", {}).get("role", "md")
        user = q("SELECT * FROM users WHERE shop_id=? AND role=?", (sid, role), one=True)
        if user:
            session["user"] = user
    return redirect("/dashboard")

@app.route("/add-sale", methods=["POST"])
def add_sale():
    q("INSERT INTO sales (shop_id,item,amount,qty,seller,date) VALUES (?,?,?,?,?,?)", (session["shop_id"], request.form.get("item"), float(request.form.get("amount") or 0), int(request.form.get("qty") or 1), session["user"]["name"], str(date.today())), commit=True)
    return redirect("/dashboard")

@app.route("/add-report", methods=["POST"])
def add_report():
    f = request.form
    q("INSERT INTO reports (shop_id,date,opening,closing,sales,purchases,expenditure,profit,bad_debt,debtors) VALUES (?,?,?,?,?,?,?,?,?,?)", (session["shop_id"], str(date.today()), float(f.get("opening") or 0), float(f.get("closing") or 0), float(f.get("sales") or 0), float(f.get("purchases") or 0), float(f.get("expenditure") or 0), float(f.get("profit") or 0), float(f.get("bad_debt") or 0), float(f.get("debtors") or 0)), commit=True)
    return redirect("/dashboard")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

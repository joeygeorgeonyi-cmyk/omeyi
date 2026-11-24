import os, sqlite3
from datetime import datetime, timedelta, date
from flask import Flask, request, redirect, session, g, url_for
import urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-v10")
app.permanent_session_lifetime = timedelta(hours=12)

DB = "shop.db"
PAYMENT_BANK = "OPay"
PAYMENT_ACCOUNT = "08037372296"
PAYMENT_NAME = "Joseph George"

# ---------- DB ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE,
         password TEXT, role TEXT, shop_id TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shops
        (shop_id TEXT PRIMARY KEY, name TEXT, owner TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS inventory
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, item TEXT,
         qty REAL, price REAL, expiry TEXT, low_level REAL DEFAULT 5)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sales
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, item TEXT,
         qty REAL, price REAL, total REAL, date TEXT, created_by TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS purchases
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, item TEXT,
         qty REAL, price REAL, total REAL, date TEXT, created_by TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS debtors
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, name TEXT,
         amount REAL, status TEXT, date TEXT, created_by TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS creditors
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, name TEXT,
         amount REAL, status TEXT, date TEXT, created_by TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS losses
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, item TEXT,
         qty REAL, amount REAL, date TEXT, created_by TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS requests
        (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id TEXT, item TEXT,
         qty REAL, date TEXT, created_by TEXT, status TEXT DEFAULT 'Pending')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shop_settings
        (shop_id TEXT PRIMARY KEY, md_phone TEXT, manager_phone TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS subscription_plans
        (name TEXT PRIMARY KEY, amount REAL, days INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS subscriptions
        (shop_id TEXT PRIMARY KEY, plan TEXT, expires TEXT, status TEXT)""")
    # Default plans
    for n, a, d in [("Monthly", 5000, 30), ("Quarterly", 12000, 90), ("Yearly", 40000, 365)]:
        conn.execute("INSERT OR IGNORE INTO subscription_plans VALUES (?,?,?)", (n, a, d))
    # Default superadmin
    conn.execute("INSERT OR IGNORE INTO users (username,password,role,shop_id) VALUES (?,?,?,?)",
                 ("superadmin", "admin123", "superadmin", "ALL"))
    conn.commit()
    conn.close()

init_db()

# ---------- Helpers ----------
def safe(r, k, default=0):
    try:
        v = r[k]
        return v if v is not None else default
    except Exception:
        return default

def fmt(v):
    try:
        return f"₦{float(v):,.0f}"
    except Exception:
        return "₦0"

def today_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def get_plans():
    conn = get_db()
    rows = conn.execute("SELECT * FROM subscription_plans ORDER BY days").fetchall()
    if not rows:
        return [{"name": "Monthly", "amount": 5000, "days": 30}]
    return [dict(r) for r in rows]

def shop_contacts(shop_id):
    if not shop_id:
        return {}
    conn = get_db()
    r = conn.execute("SELECT * FROM shop_settings WHERE shop_id=?", (shop_id,)).fetchone()
    return dict(r) if r else {}

def upsert_settings(shop_id, md_phone, manager_phone):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO shop_settings VALUES (?,?,?)",
                 (shop_id, (md_phone or "").strip(), (manager_phone or "").strip()))
    conn.commit()

def wa_link(phone, msg):
    p = "".join(filter(str.isdigit, str(phone or "")))
    if p.startswith("0"):
        p = "234" + p[1:]
    return f"https://wa.me/{p}?text={urllib.parse.quote(msg)}"

def is_expired(shop_id):
    if not shop_id or shop_id == "ALL":
        return False
    conn = get_db()
    r = conn.execute("SELECT * FROM subscriptions WHERE shop_id=?", (shop_id,)).fetchone()
    if not r:
        return False
    try:
        return datetime.now() > datetime.strptime(r["expires"], "%Y-%m-%d")
    except Exception:
        return False

STYLE = """<style>
body{font-family:Arial;background:#f2f2f2;margin:0;padding:10px}
.card{background:#fff;padding:15px;border-radius:10px;margin:10px 0;box-shadow:0 1px 4px #ccc}
input,select{width:100%;padding:10px;margin:6px 0;border:1px solid #ccc;border-radius:6px;box-sizing:border-box}
button{background:#111;color:#fff;padding:11px 18px;border:none;border-radius:6px;width:100%;font-size:16px}
button.green{background:#25D366} button.blue{background:#128C7E} button.red{background:#c0392b}
a{text-decoration:none;color:#111} table{width:100%;border-collapse:collapse}
th,td{border:1px solid #ddd;padding:7px;text-align:left;font-size:14px}
.muted{color:#777;font-size:13px} .warn{background:#fff3cd} .danger{background:#fdecea}
.top{background:#111;color:#fff;padding:12px;border-radius:8px}
</style>"""

def top(title, sub=""):
    role = session.get("role", "")
    shop = session.get("shop_id", "")
    return f"""<div class="top"><b>{title}</b><br><span style="font-size:13px">{sub} | {role} | {shop}</span></div>"""

def end():
    return """<br><p class="muted" style="text-align:center">V10 Final • MD & Manager WhatsApp ONLY</p>"""

def logout_bar():
    return """<br><a href="/logout"><button class="red">Logout</button></a>"""

def blocked_msg(msg="You are not allowed to view this page."):
    return STYLE + top("Blocked") + f"""<div class="card danger"><b>⛔ Blocked</b><p>{msg}</p><a href="/shop">Go Back</a></div>""" + end()

# ---------- Auth ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
        if user:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["shop_id"] = user["shop_id"]
            if user["role"] == "superadmin":
                return redirect("/superadmin")
            if is_expired(user["shop_id"]):
                return redirect("/subscription")
            return redirect("/shop")
        return STYLE + top("Login") + """<div class="card danger">Wrong username / password</div><a href="/">Try Again</a>""" + end()
    return STYLE + top("Login", "Shop Management System") + """<div class="card">
    <form method="post"><label>Username</label><input name="username" required>
    <label>Password</label><input name="password" type="password" required>
    <button>Login</button></form></div>""" + end()

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/superadmin")
def superadmin():
    if session.get("role") != "superadmin":
        return blocked_msg()
    conn = get_db()
    shops = conn.execute("SELECT * FROM shops").fetchall()
    users = conn.execute("SELECT * FROM users").fetchall()
    s_rows = "".join([f"<tr><td>{r['shop_id']}</td><td>{r['name']}</td><td>{r['owner']}</td></tr>" for r in shops])
    u_rows = "".join([f"<tr><td>{r['username']}</td><td>{r['role']}</td><td>{r['shop_id']}</td></tr>" for r in users])
    return STYLE + top("Super Admin", "Manage Shops & Users") + f"""<div class="card">
    <h3>Create Shop</h3><form action="/create-shop" method="post">
    <input name="shop_id" placeholder="Shop ID e.g. SHOP1" required>
    <input name="name" placeholder="Shop Name" required>
    <input name="owner" placeholder="Owner Name" required><button>Create Shop</button></form></div>
    <div class="card"><h3>Create User</h3><form action="/create-user" method="post">
    <input name="username" placeholder="Username" required>
    <input name="password" placeholder="Password" required>
    <select name="role"><option>owner</option><option>manager</option><option>sales</option><option>admin</option></select>
    <input name="shop_id" placeholder="Shop ID" required><button>Create User</button></form></div>
    <div class="card"><h3>Shops</h3><table><tr><th>ID</th><th>Name</th><th>Owner</th></tr>{s_rows}</table></div>
    <div class="card"><h3>Users</h3><table><tr><th>Username</th><th>Role</th><th>Shop</th></tr>{u_rows}</table></div>
    <a href="/subscription">Subscription Plans</a> | <a href="/shop">Go to Shop</a>""" + logout_bar() + end()

@app.route("/create-shop", methods=["POST"])
def create_shop():
    if session.get("role") != "superadmin":
        return blocked_msg()
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO shops VALUES (?,?,?)",
                 (request.form.get("shop_id"), request.form.get("name"), request.form.get("owner")))
    conn.commit()
    return redirect("/superadmin")

@app.route("/create-user", methods=["POST"])
def create_user():
    if session.get("role") != "superadmin":
        return blocked_msg()
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username,password,role,shop_id) VALUES (?,?,?,?)",
                     (request.form.get("username"), request.form.get("password"),
                      request.form.get("role"), request.form.get("shop_id")))
        conn.commit()
    except Exception as e:
        return f"Error: {e} <br><a href='/superadmin'>Back</a>"
    return redirect("/superadmin")

# ---------- Shop Dashboard ----------
@app.route("/shop")
def shop():
    if "user_id" not in session:
        return redirect("/")
    if session.get("role") == "superadmin":
        return redirect("/superadmin")
    shop_id = session.get("shop_id")
    conn = get_db()
    inv = conn.execute("SELECT * FROM inventory WHERE shop_id=? ORDER BY item", (shop_id,)).fetchall()
    sales = conn.execute("SELECT * FROM sales WHERE shop_id=? ORDER BY date DESC LIMIT 10", (shop_id,)).fetchall()
    total_sales = conn.execute("SELECT COALESCE(SUM(total),0) as t FROM sales WHERE shop_id=?", (shop_id,)).fetchone()["t"]
    total_debt = conn.execute("SELECT COALESCE(SUM(amount),0) as t FROM debtors WHERE shop_id=? AND status!='Settled'", (shop_id,)).fetchone()["t"]
    low = [r for r in inv if float(safe(r, "qty")) <= float(safe(r, "low_level", 5))]
    expiring = []
    for r in inv:
        try:
            if r["expiry"] and (datetime.strptime(r["expiry"], "%Y-%m-%d") - datetime.now()).days <= 30:
                expiring.append(r)
        except Exception:
            pass
    inv_rows = "".join([f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'price'))}</td><td>{r['expiry'] or ''}</td></tr>" for r in inv])
    sale_rows = "".join([f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td></tr>" for r in sales])
    warn = ""
    if low:
        warn += f"<div class='card warn'><b>⚠️ Low Stock:</b> {', '.join([r['item'] for r in low])}</div>"
    if expiring:
        warn += f"<div class='card warn'><b>⏰ Expiring Soon (30 days):</b> {', '.join([r['item'] for r in expiring])}</div>"
    role = session.get("role")
    admin_links = ""
    if role in ["owner", "manager"]:
        admin_links = """<a href="/print-transactions"><button>🖨️ Print Transactions</button></a><br><br>
        <a href="/shop-settings"><button>⚙️ WhatsApp Settings</button></a><br><br>"""
    return STYLE + top("Shop Dashboard", f"Total Sales: {fmt(total_sales)} | Debt Outstanding: {fmt(total_debt)}") + f"""{warn}
    <div class="card"><h3>Quick Actions</h3>
    <a href="/sell"><button>Sell Item</button></a><br><br>
    <a href="/add-purchase"><button>Add Purchase</button></a><br><br>
    <a href="/add-debtor"><button>Add Debtor</button></a><br><br>
    <a href="/add-creditor"><button>Add Creditor</button></a><br><br>
    <a href="/add-loss"><button>Add Loss / Damage</button></a><br><br>
    <a href="/add-request"><button>Request Stock</button></a><br><br>
    {admin_links}
    <a href="/subscription"><button>Subscription</button></a></div>
    <div class="card"><h3>Inventory</h3><table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Expiry</th></tr>{inv_rows}</table></div>
    <div class="card"><h3>Recent Sales</h3><table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th></tr>{sale_rows}</table></div>""" + logout_bar() + end()
# ---------- Sell ----------
@app.route("/sell", methods=["GET", "POST"])
def sell():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        item = request.form.get("item", "").strip()
        try:
            qty = float(request.form.get("qty", 0) or 0)
        except Exception:
            qty = 0
        inv = conn.execute("SELECT * FROM inventory WHERE shop_id=? AND item=?", (shop_id, item)).fetchone()
        if not inv:
            return STYLE + top("Sell") + """<div class="card danger">Item not found in inventory.</div><a href="/sell">Back</a>""" + end()
        if float(safe(inv, "qty")) < qty:
            return STYLE + top("Sell") + f"""<div class="card danger">Not enough stock. Available: {safe(inv,'qty')}</div><a href="/sell">Back</a>""" + end()
        price = float(safe(inv, "price"))
        total = price * qty
        conn.execute("UPDATE inventory SET qty=qty-? WHERE id=?", (qty, inv["id"]))
        cur = conn.execute("INSERT INTO sales (shop_id,item,qty,price,total,date,created_by) VALUES (?,?,?,?,?,?,?)",
                           (shop_id, item, qty, price, total, today_str(), session.get("username")))
        conn.commit()
        sale_id = cur.lastrowid
        return STYLE + top("Sale Done") + f"""<div class="card"><h3>✅ Sold: {item} x {qty} = {fmt(total)}</h3>
        <a href="/sale-whatsapp/{sale_id}"><button class="green">Send to MD & Manager on WhatsApp</button></a><br><br>
        <a href="/shop">Go Back</a></div>""" + end()
    inv = conn.execute("SELECT * FROM inventory WHERE shop_id=?", (shop_id,)).fetchall()
    opts = "".join([f"<option value='{r['item']}'>{r['item']} - Stock: {r['qty']} - {fmt(safe(r,'price'))}</option>" for r in inv])
    return STYLE + top("Sell Item") + f"""<div class="card"><form method="post">
    <label>Item</label><select name="item" required>{opts}</select>
    <label>Qty</label><input name="qty" type="number" step="0.01" min="0.01" required>
    <button>Sell</button></form></div>""" + end()

# ---------- Purchase ----------
@app.route("/add-purchase", methods=["GET", "POST"])
def add_purchase():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        item = request.form.get("item", "").strip()
        qty = float(request.form.get("qty", 0) or 0)
        price = float(request.form.get("price", 0) or 0)
        expiry = request.form.get("expiry", "") or None
        total = qty * price
        cur = conn.execute("INSERT INTO purchases (shop_id,item,qty,price,total,date,created_by) VALUES (?,?,?,?,?,?,?)",
                           (shop_id, item, qty, price, total, today_str(), session.get("username")))
        inv = conn.execute("SELECT * FROM inventory WHERE shop_id=? AND item=?", (shop_id, item)).fetchone()
        if inv:
            conn.execute("UPDATE inventory SET qty=qty+?, price=?, expiry=? WHERE id=?", (qty, price, expiry, inv["id"]))
        else:
            conn.execute("INSERT INTO inventory (shop_id,item,qty,price,expiry) VALUES (?,?,?,?,?)",
                         (shop_id, item, qty, price, expiry))
        conn.commit()
        pid = cur.lastrowid
        return STYLE + top("Purchase Saved") + f"""<div class="card"><h3>✅ Purchase: {item} x {qty} = {fmt(total)}</h3>
        <a href="/purchase-whatsapp/{pid}"><button class="green">Send to MD & Manager on WhatsApp</button></a><br><br>
        <a href="/shop">Go Back</a></div>""" + end()
    return STYLE + top("Add Purchase") + """<div class="card"><form method="post">
    <label>Item</label><input name="item" required>
    <label>Qty</label><input name="qty" type="number" step="0.01" required>
    <label>Price per unit (₦)</label><input name="price" type="number" step="0.01" required>
    <label>Expiry (optional)</label><input name="expiry" type="date">
    <button>Save Purchase</button></form></div>""" + end()

# ---------- Debtors ----------
@app.route("/add-debtor", methods=["GET", "POST"])
def add_debtor():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        amount = float(request.form.get("amount", 0) or 0)
        cur = conn.execute("INSERT INTO debtors (shop_id,name,amount,status,date,created_by) VALUES (?,?,?,?,?,?)",
                           (shop_id, name, amount, "Owing", today_str(), session.get("username")))
        conn.commit()
        did = cur.lastrowid
        return STYLE + top("Debtor Saved") + f"""<div class="card"><h3>✅ Debtor: {name} - {fmt(amount)}</h3>
        <a href="/debtor-whatsapp/{did}"><button class="green">Send to MD & Manager on WhatsApp</button></a><br><br>
        <a href="/shop">Go Back</a></div>""" + end()
    rows = conn.execute("SELECT * FROM debtors WHERE shop_id=? ORDER BY date DESC LIMIT 20", (shop_id,)).fetchall()
    rws = "".join([f"<tr><td>{r['name']}</td><td>{fmt(safe(r,'amount'))}</td><td>{r['status']}</td><td><a href='/settle-debtor/{r['id']}'>Settle</a></td></tr>" for r in rows])
    return STYLE + top("Add Debtor") + f"""<div class="card"><form method="post">
    <label>Name</label><input name="name" required>
    <label>Amount (₦)</label><input name="amount" type="number" step="0.01" required>
    <button>Save Debtor</button></form></div>
    <div class="card"><h3>Recent Debtors</h3><table><tr><th>Name</th><th>Amount</th><th>Status</th><th>Action</th></tr>{rws}</table></div>""" + end()

@app.route("/settle-debtor/<int:did>")
def settle_debtor(did):
    if "user_id" not in session:
        return redirect("/")
    conn = get_db()
    conn.execute("UPDATE debtors SET status='Settled' WHERE id=?", (did,))
    conn.commit()
    return redirect("/add-debtor")

# ---------- Creditors ----------
@app.route("/add-creditor", methods=["GET", "POST"])
def add_creditor():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        amount = float(request.form.get("amount", 0) or 0)
        cur = conn.execute("INSERT INTO creditors (shop_id,name,amount,status,date,created_by) VALUES (?,?,?,?,?,?)",
                           (shop_id, name, amount, "Owing", today_str(), session.get("username")))
        conn.commit()
        cid = cur.lastrowid
        return STYLE + top("Creditor Saved") + f"""<div class="card"><h3>✅ Creditor: {name} - {fmt(amount)}</h3>
        <a href="/creditor-whatsapp/{cid}"><button class="green">Send to MD & Manager on WhatsApp</button></a><br><br>
        <a href="/shop">Go Back</a></div>""" + end()
    rows = conn.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY date DESC LIMIT 20", (shop_id,)).fetchall()
    rws = "".join([f"<tr><td>{r['name']}</td><td>{fmt(safe(r,'amount'))}</td><td>{r['status']}</td></tr>" for r in rows])
    return STYLE + top("Add Creditor") + f"""<div class="card"><form method="post">
    <label>Name</label><input name="name" required>
    <label>Amount (₦)</label><input name="amount" type="number" step="0.01" required>
    <button>Save Creditor</button></form></div>
    <div class="card"><h3>Recent Creditors</h3><table><tr><th>Name</th><th>Amount</th><th>Status</th></tr>{rws}</table></div>""" + end()

# ---------- Loss / Request ----------
@app.route("/add-loss", methods=["GET", "POST"])
def add_loss():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        item = request.form.get("item", "").strip()
        qty = float(request.form.get("qty", 0) or 0)
        amount = float(request.form.get("amount", 0) or 0)
        conn.execute("INSERT INTO losses (shop_id,item,qty,amount,date,created_by) VALUES (?,?,?,?,?,?)",
                     (shop_id, item, qty, amount, today_str(), session.get("username")))
        inv = conn.execute("SELECT * FROM inventory WHERE shop_id=? AND item=?", (shop_id, item)).fetchone()
        if inv:
            conn.execute("UPDATE inventory SET qty=MAX(0, qty-?) WHERE id=?", (qty, inv["id"]))
        conn.commit()
        return redirect("/shop")
    return STYLE + top("Add Loss / Damage") + """<div class="card"><form method="post">
    <label>Item</label><input name="item" required>
    <label>Qty Lost</label><input name="qty" type="number" step="0.01" required>
    <label>Amount (₦)</label><input name="amount" type="number" step="0.01" required>
    <button>Save Loss</button></form></div>""" + end()

@app.route("/add-request", methods=["GET", "POST"])
def add_request():
    if "user_id" not in session:
        return redirect("/")
    shop_id = session.get("shop_id")
    conn = get_db()
    if request.method == "POST":
        conn.execute("INSERT INTO requests (shop_id,item,qty,date,created_by) VALUES (?,?,?,?,?)",
                     (shop_id, request.form.get("item"), float(request.form.get("qty", 0) or 0),
                      today_str(), session.get("username")))
        conn.commit()
        return redirect("/shop")
    return STYLE + top("Request Stock") + """<div class="card"><form method="post">
    <label>Item Needed</label><input name="item" required>
    <label>Qty</label><input name="qty" type="number" step="0.01" required>
    <button>Send Request</button></form></div>""" + end()

# ---------- Subscription ----------
@app.route("/subscription")
def subscription():
    if "user_id" not in session:
        return redirect("/")
    plans = get_plans()
    cards = ""
    for p in plans:
        cards += f"""<div class="card"><h3>{p['name']} - {fmt(p['amount'])} / {p['days']} days</h3>
        <a href="/subscription/pay?plan={p['name']}"><button>Choose {p['name']}</button></a></div>"""
    html = STYLE + top("Subscription", "Choose a plan to continue") + cards
    html += f"""<div class="card"><b>How to pay:</b><br>1. Transfer to {PAYMENT_BANK} <b>{PAYMENT_ACCOUNT}</b> ({PAYMENT_NAME})<br>2. Click I Don Pay<br>3. Super Admin go confirm am.</div><a href="/shop">Go Back</a>""" + end()
    return html

@app.route("/subscription/pay")
def sub_pay():
    plan = request.args.get("plan", "")
    return STYLE + top("Payment Submitted", "") + f"""<div class="card"><h3>Payment Submitted</h3>
    <p>Plan: {plan}<br>Pay to: {PAYMENT_BANK} - {PAYMENT_ACCOUNT} - {PAYMENT_NAME}</p>
    <p class="muted">Super Admin will confirm your payment and activate your subscription.</p>
    <a href="/shop">Go Back</a></div>""" + end()

# ---------- Shop Settings ----------
@app.route("/shop-settings", methods=["GET", "POST"])
def shop_settings():
    if session.get("role") == "sales":
        return blocked_msg("Salesperson cannot view WhatsApp Settings.")
    if session.get("role") not in ["owner", "manager", "admin", "superadmin"]:
        return blocked_msg()
    if request.method == "POST":
        upsert_settings(session.get("shop_id"), request.form.get("md_phone", ""), request.form.get("manager_phone", ""))
        if session.get("role") == "superadmin":
            conn = get_db()
            conn.execute("DELETE FROM subscription_plans")
            for n, a, d in [("Monthly", request.form.get("p1"), 30), ("Quarterly", request.form.get("p2"), 90), ("Yearly", request.form.get("p3"), 365)]:
                if a:
                    try:
                        conn.execute("INSERT INTO subscription_plans VALUES (?,?,?)", (n, float(a), d))
                    except Exception:
                        pass
            conn.commit()
        return redirect("/shop")
    plans = get_plans()
    # Ensure 3 plans for form
    while len(plans) < 3:
        plans.append({"name": "Plan", "amount": 0, "days": 30})
    c = shop_contacts(session.get("shop_id"))
    return STYLE + top("WhatsApp Settings", "Notifications ONLY to MD & Manager") + f"""<div class="card"><form method="post">
    <label>MD/CEO WhatsApp Number</label><input name="md_phone" value="{c.get('md_phone','')}" placeholder="e.g. 08037372296">
    <label>Manager WhatsApp Number</label><input name="manager_phone" value="{c.get('manager_phone','')}" placeholder="e.g. 080...">
    <label>Monthly Price (₦)</label><input name="p1" value="{plans[0]['amount']:.0f}">
    <label>Quarterly Price (₦)</label><input name="p2" value="{plans[1]['amount']:.0f}">
    <label>Yearly Price (₦)</label><input name="p3" value="{plans[2]['amount']:.0f}">
    <p class="muted">WhatsApp goes to MD & Manager ONLY for: Sales, Purchases, Debtors, Creditors, Settling, Expiry, Stock Levels.</p>
    <button>Save Settings</button></form></div>""" + end()

# ---------- WhatsApp Notify ----------
def notify_page(title, msg):
    c = shop_contacts(session.get("shop_id"))
    links = ""
    if c.get("md_phone"):
        links += f"<a href='{wa_link(c['md_phone'], msg)}'><button class='green'>Send to MD/CEO on WhatsApp</button></a><br><br>"
    if c.get("manager_phone"):
        links += f"<a href='{wa_link(c['manager_phone'], msg)}'><button class='blue'>Send to Manager on WhatsApp</button></a>"
    if not links:
        links = "<p class='muted'>No WhatsApp numbers yet. Ask Owner/Manager to set them in WhatsApp Settings.</p>"
    return STYLE + top(title, "Notifications to MD & Manager ONLY") + f"<div class='card'><p>{msg}</p>{links}<br><a href='/shop'>Go Back</a></div>" + end()

@app.route("/sale-whatsapp/<int:sale_id>")
def sale_whatsapp(sale_id):
    conn = get_db()
    s = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    if not s:
        return "Sale not found"
    return notify_page("WhatsApp - Sale", f"🔔 New Sale: {s['item']} x{s['qty']} = {fmt(safe(s,'total'))} | Shop {s['shop_id']} | By {s['created_by']} | {s['date']}")

@app.route("/purchase-whatsapp/<int:pid>")
def purchase_whatsapp(pid):
    conn = get_db()
    s = conn.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
    if not s:
        return "Purchase not found"
    return notify_page("WhatsApp - Purchase", f"🔔 New Purchase: {s['item']} x{s['qty']} = {fmt(safe(s,'total'))} | Shop {s['shop_id']} | By {s['created_by']} | {s['date']}")

@app.route("/debtor-whatsapp/<int:did>")
def debtor_whatsapp(did):
    conn = get_db()
    s = conn.execute("SELECT * FROM debtors WHERE id=?", (did,)).fetchone()
    if not s:
        return "Debtor not found"
    return notify_page("WhatsApp - Debtor", f"🔔 Debtor Update: {s['name']} - {fmt(safe(s,'amount'))} - {s['status']} | Shop {s['shop_id']} | {s['date']}")

@app.route("/creditor-whatsapp/<int:cid>")
def creditor_whatsapp(cid):
    conn = get_db()
    s = conn.execute("SELECT * FROM creditors WHERE id=?", (cid,)).fetchone()
    if not s:
        return "Creditor not found"
    return notify_page("WhatsApp - Creditor", f"🔔 Creditor Update: {s['name']} - {fmt(safe(s,'amount'))} - {s['status']} | Shop {s['shop_id']} | {s['date']}")

# ---------- Print ----------
@app.route("/print-transactions")
def print_transactions():
    if session.get("role") not in ["owner", "manager"]:
        return blocked_msg("Only MD/CEO & Manager fit print.")
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales WHERE shop_id=? ORDER BY date DESC LIMIT 200", (session.get("shop_id"),)).fetchall()
    rows = "".join([f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td><td>{r['created_by']}</td></tr>" for r in sales])
    return STYLE + top("Transactions - Print / PDF", "Only MD/CEO & Manager") + f"""<div class="card">
    <button onclick="window.print()">🖨️ Print / Save as PDF</button><br><br>
    <table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th><th>By</th></tr>{rows}</table></div>""" + logout_bar() + end()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

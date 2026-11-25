# Omeyi - V10 Clean Rebuild - All 16 Points
# Omeyi = platform name ONLY. Never a shop.
# Shop = ONLY wetin Super Admin create. No default shop.

from flask import Flask, request, redirect, session, g
import datetime, os, sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "omeyi-secret-key")
DB = "shop.db"
APP_URL = "https://omeyi.onrender.com"
PAYMENT_BANK = "Opay"; PAYMENT_ACCOUNT = "8037372296"; PAYMENT_NAME = "Joseph George"
LOSS_REASONS = ["Expiry","Broken Seal/Others","Broken Bottles","Damaged","Inferior Products"]
DEBTOR_REASONS = ["Regular/Loyal Customers","Failed POS Transactions","Network Problem","Cut Price","Bonanza","Others"]
TIMELINES = ["1-3 days","4-7 days","8-10 days","10-14 days"]

def get_db():
    if "db" not in g:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; g.db = c
    return g.db
@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def safe(r,*names):
    d = dict(r) if r is not None else {}
    for n in names:
        if n in d and d[n] is not None: return d[n]
    return 0
def today_str(): return datetime.date.today().isoformat()
def fmt(n):
    try: return f"\u20a6{float(n or 0):,.0f}"
    except: return "\u20a60"
def display_role(r): return {'owner':'MD/CEO','manager':'Manager','sales':'Salesperson','admin':'Admin','superadmin':'Super Admin'}.get(r,r or '')

def init_db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY, name TEXT UNIQUE, admin_user TEXT, admin_pass TEXT, is_active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, shop_id INTEGER, username TEXT, password TEXT, role TEXT, name TEXT, must_change INTEGER DEFAULT 1, pwd_changed_at TEXT, UNIQUE(username, shop_id))")
    c.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, qty REAL, price REAL, cost_price REAL, selling_price REAL, total REAL, expiry_date TEXT, min_stock REAL DEFAULT 0, max_stock REAL DEFAULT 0, created_by TEXT, created_by_role TEXT, date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, qty REAL, price REAL, cost_price REAL, selling_price REAL, total REAL, created_by TEXT, created_by_role TEXT, date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS debtors (id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, amount REAL, phone TEXT DEFAULT '', item TEXT DEFAULT '', reason TEXT DEFAULT '', status TEXT DEFAULT 'Owing', timeframe TEXT DEFAULT '', paid_amount REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS creditors (id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, amount REAL, phone TEXT DEFAULT '', item TEXT DEFAULT '', reason TEXT DEFAULT '', status TEXT DEFAULT 'Owing', timeframe TEXT DEFAULT '', paid_amount REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS losses (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, amount REAL, note TEXT DEFAULT '', reason TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, amount REAL, note TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, shop_id INTEGER, type TEXT, title TEXT, amount REAL DEFAULT 0, note TEXT DEFAULT '', items TEXT DEFAULT '', status TEXT DEFAULT 'Pending', owner_feedback TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, shop_id INTEGER, period TEXT, period_label TEXT, summary TEXT DEFAULT '', status TEXT DEFAULT 'Submitted', manager_remark TEXT DEFAULT '', owner_remark TEXT DEFAULT '', created_by TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS alert_requests (id INTEGER PRIMARY KEY, shop_id INTEGER, alert_item TEXT DEFAULT '', alert_type TEXT DEFAULT '', manager_message TEXT DEFAULT '', status TEXT DEFAULT 'Pending', owner_remark TEXT DEFAULT '', created_by TEXT DEFAULT '', date TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS shop_settings (shop_id INTEGER PRIMARY KEY, md_phone TEXT DEFAULT '', manager_phone TEXT DEFAULT '')")
    try: c.execute("DELETE FROM shops WHERE UPPER(name)='OMEYI'")
    except: pass
    c.commit(); c.close()
init_db()

def period_start(period):
    t = datetime.date.today()
    if period == "today": return t.isoformat()
    if period == "week": return (t - datetime.timedelta(days=t.weekday())).isoformat()
    if period == "month": return t.replace(day=1).isoformat()
    if period == "quarter": return t.replace(month=((t.month-1)//3)*3+1, day=1).isoformat()
    if period == "year": return t.replace(month=1, day=1).isoformat()
    return "0000-01-01"
def period_totals(rows, date_field="date"):
    t = datetime.date.today()
    out = {"today":0,"week":0,"month":0,"quarter":0,"year":0}
    for r in rows:
        try: d = datetime.date.fromisoformat(str(safe(r,date_field) or "")[:10])
        except: continue
        amt = float(safe(r,"total", "amount") or 0)
        if d == t: out["today"] += amt
        if d >= t - datetime.timedelta(days=t.weekday()): out["week"] += amt
        if d.year == t.year and d.month == t.month: out["month"] += amt
        if d.year == t.year and (d.month-1)//3 == (t.month-1)//3: out["quarter"] += amt
        if d.year == t.year: out["year"] += amt
    return out

STYLE = """<style>*{box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#eaf0f7;color:#1e293b;padding-bottom:40px}.top{background:linear-gradient(135deg,#0b3d91,#0b5ed7 55%,#0ea5e9);color:#fff;padding:18px 16px}.omeyi{font-size:12px;color:#bfdbfe;margin:0;letter-spacing:3px;text-transform:uppercase;font-weight:800}h1{font-size:24px;margin:6px 0 2px}.sub{color:#dbeafe;font-size:13px;margin:0}.wrap{padding:0 12px 30px;max-width:960px;margin:auto}.card{background:#fff;padding:16px;border-radius:16px;margin-bottom:14px;box-shadow:0 4px 14px rgba(11,61,145,.10);border:1px solid #dbeafe}label{font-size:12px;font-weight:800;color:#0b3d91;text-transform:uppercase}input,select,textarea{padding:12px;margin:6px 0 11px;width:100%;border:1.5px solid #cbd5e1;border-radius:10px;font-size:14px;background:#f8fafc}button{padding:13px;background:#0b3d91;color:#fff;border:none;border-radius:11px;cursor:pointer;width:100%;font-weight:800}button.green{background:#16a34a}button.orange{background:#ea580c}button.blue{background:#0b5ed7}button.red{background:#dc2626}button.small{padding:8px 11px;width:auto;font-size:12px}table{width:100%;border-collapse:collapse}th{background:#0b3d91;color:#fff;padding:11px 8px;font-size:11px;text-align:left}td{padding:11px 8px;font-size:13px;border-bottom:1px solid #e2e8f0}.section{font-size:18px;font-weight:900;margin:20px 2px 10px;color:#0b3d91}.muted{font-size:12px;color:#64748b}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.footer{text-align:center;color:#64748b;font-size:12px;padding:18px 0}.row-card{background:#fff;padding:13px;border-radius:12px;margin-bottom:9px;display:flex;justify-content:space-between;border-left:6px solid #0b5ed7}.meter{background:#e2e8f0;height:12px;border-radius:8px;overflow:hidden}.meter>div{background:linear-gradient(90deg,#0b3d91,#0ea5e9);height:12px}.logout{background:#dc2626!important}.pie{width:150px;height:150px;border-radius:50%;margin:auto}</style>"""
FOOTER = '<div class="footer">\u00a9 Omeyi \u2022 All Rights Reserved \u2022 Powered by Omeyi Blue</div>'
def top(t,s=""): return f'<div class="top"><p class="omeyi">Omeyi</p><h1>{t}</h1><p class="sub">{s}</p></div><div class="wrap" style="margin-top:16px">'
def end(): return "</div>"+FOOTER
def logout_bar(): return """<div class="card" style="display:flex;gap:10px"><a href="/change-password" style="flex:1"><button class="blue">\U0001f511 Change Password</button></a><a href="/logout" style="flex:1"><button class="logout">\U0001f6aa LOGOUT</button></a></div>"""
def blocked_msg(m="You are not allowed to post this."): return f"{m} <a href='/shop'>Go Back</a>"

@app.route("/", methods=["GET","POST"])
def login():
    conn = get_db()
    shops = conn.execute("SELECT id, name FROM shops WHERE is_active=1 ORDER BY name").fetchall()
    shop_opts = "".join([f'<option value="{s["id"]}">{s["name"]} (ID {s["id"]})</option>' for s in shops])
    if request.method == "POST":
        shop_id_raw = request.form.get("shop_id","").strip()
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if u == "superadmin" and p == "omeyi123":
            session.clear(); session["user"]="superadmin"; session["username"]="superadmin"; session["role"]="superadmin"; session["shop"]="ALL"; session["shop_id"]=0; session["shop_name"]="ALL"; session["name"]="Super Admin"; session["is_super"]=True
            return redirect("/superadmin")
        if not shop_id_raw:
            return STYLE+top("Login","Select Shop")+'<p style="color:red">Please select Shop / Company from list first.</p><a href="/">Try again</a>'+end()
        try: shop_id = int(shop_id_raw)
        except: return STYLE+top("Login","Wrong username or password")+end()
        srow = conn.execute("SELECT * FROM shops WHERE id=? AND is_active=1",(shop_id,)).fetchone()
        if not srow: return STYLE+top("Login","Wrong username or password")+end()
        shop_name = dict(srow).get("name") or ""
        r = conn.execute("SELECT * FROM users WHERE username=? AND shop_id=?",(u,shop_id)).fetchone()
        if not r: return STYLE+top("Login","Wrong username or password")+end()
        d = dict(r); stored = str(d.get("password") or "")
        ok = False
        try: ok = check_password_hash(stored,p)
        except: ok = False
        if not ok and stored == p: ok = True
        if not ok: return STYLE+top("Login","Wrong username or password")+end()
        session.clear(); session["user"]=u; session["username"]=u; session["role"]=d.get("role"); session["name"]=d.get("name") or u; session["shop"]=shop_name; session["shop_id"]=shop_id; session["shop_name"]=shop_name; session["is_super"]=False
        return redirect("/shop")
    # FIXED: NO required on shop dropdown, so Super Admin can login without selecting shop
    return STYLE+top("Login","Welcome back")+f'<form method="POST"><label>Shop / Company - Select from list (Staff only - Super Admin leave as -- Select Shop --)</label><select name="shop_id"><option value="">-- Select Shop --</option>{shop_opts}</select><label>Username</label><input name="username" placeholder="USERNAME" required><label>Password</label><input name="password" type="password" placeholder="PASSWORD" required><button>LOGIN</button></form><p class="muted">Super Admin: superadmin / omeyi123 - leave Shop as -- Select Shop --<br>Staff: Select YOUR shop from dropdown, then your username + password</p>'+end()

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

@app.route("/change-password", methods=["GET","POST"])
def change_password():
    if 'role' not in session: return redirect("/")
    if request.method == "POST":
        old = request.form.get("old_password",""); new = request.form.get("new_password",""); conn = get_db()
        r = conn.execute("SELECT * FROM users WHERE username=?",(session.get('username'),)).fetchone()
        if r:
            d = dict(r); stored = str(d.get("password") or ""); ok=False
            try: ok = check_password_hash(stored,old)
            except: ok=False
            if ok or stored == old:
                conn.execute("UPDATE users SET password=?, must_change=0, pwd_changed_at=? WHERE username=? AND shop_id=?",(generate_password_hash(new),today_str(),session.get('username'),session.get('shop_id'))); conn.commit(); return redirect("/shop")
        return STYLE+top("Change Password","Wrong old password")+"<div class='card'><p>Old password no match. <a href='/change-password'>Try again</a></p></div>"+end()
    return STYLE+top("Change Password","All staff fit change password.")+f"""<div class="card"><form method="post"><label>Old Password</label><input name="old_password" type="password" required><label>New Password</label><input name="new_password" type="password" required><button class="green">Change Password</button></form></div>"""+logout_bar()+end()

@app.route("/superadmin")
def superadmin():
    if session.get('role') != 'superadmin': return redirect("/")
    conn = get_db(); shops = conn.execute("SELECT * FROM shops ORDER BY id DESC").fetchall()
    traffic=[]
    for s in shops:
        sc = conn.execute("SELECT COUNT(*) as c FROM sales WHERE shop_id=?",(s["id"],)).fetchone(); pc = conn.execute("SELECT COUNT(*) as c FROM purchases WHERE shop_id=?",(s["id"],)).fetchone()
        total = int(safe(sc,'c'))+int(safe(pc,'c')); traffic.append({"shop":s,"total":total,"sales":int(safe(sc,'c')),"purchases":int(safe(pc,'c'))})
    traffic_sorted = sorted(traffic, key=lambda x: x["total"], reverse=True); max_t = max([t["total"] for t in traffic_sorted], default=1) or 1
    rows = "".join([f"<tr><td>{t['shop']['name']}</td><td>{t['shop']['admin_user']}</td><td>{'🟢 ON' if t['shop']['is_active'] else '🔴 OFF'}</td><td>{t['sales']} sales / {t['purchases']} purch</td><td><b>{t['total']}</b></td><td><a href='/enter-shop/{t['shop']['id']}'><b>Enter</b></a> | <a href='/edit-shop/{t['shop']['id']}'>Edit</a> | <a href='/toggle-shop/{t['shop']['id']}'>ON/OFF</a> | <a href='/delete-shop/{t['shop']['id']}' onclick=\"return confirm('Delete this shop?')\" style='color:#dc2626;font-weight:800'>Delete</a></td></tr>" for t in traffic_sorted])
    meter = "".join([f"<div class='row-card'><div><b>#{i+1} {t['shop']['name']}</b> — {t['total']} activities<br><div class='meter' style='width:220px;margin-top:6px'><div style='width:{int(t['total']/max_t*100) if max_t else 0}%'></div></div></div><b>{t['total']}</b></div>" for i,t in enumerate(traffic_sorted)])
    shop_opts = "".join([f"<option value='{s['id']}'>{s['name']} (ID {s['id']})</option>" for s in shops])
    return STYLE+top("Super Admin","Create MD & Staff, Edit, Delete, ON/OFF, Traffic")+f"""<div class="card"><b>Create Shop + MD/CEO</b><form method="post" action="/create-shop"><label>Shop Name</label><input name="name" required><label>MD/CEO Username</label><input name="admin_user" required><label>MD/CEO Password</label><input name="admin_pass" required><button>Create Shop</button></form></div><div class="card"><b>Create MD / Staff — ONLY Super Admin Creates</b><form method="post" action="/superadmin-create-user"><label>Select Shop</label><select name="shop_id">{shop_opts}</select><label>Full Name</label><input name="name" required><label>Username</label><input name="username" required><label>Password</label><input name="password" required><label>Role</label><select name="role"><option value="owner">MD/CEO</option><option value="manager">Manager</option><option value="sales">Salesperson</option><option value="admin">Admin</option></select><button class="green">Create MD / Staff</button></form></div><div class="card"><b>📊 Traffic Meter — Rank by Highest</b><br>{meter or 'No traffic yet.'}</div><div class="card"><table><tr><th>Shop</th><th>MD User</th><th>Sub</th><th>Traffic</th><th>Total</th><th>Action</th></tr>{rows}</table></div>"""+logout_bar()+end()

@app.route("/create-shop", methods=["POST"])
def create_shop():
    if session.get('role') != 'superadmin': return blocked_msg()
    conn = get_db(); name = request.form.get("name","").strip(); au = request.form.get("admin_user","").strip(); ap = request.form.get("admin_pass","").strip()
    if not name or not au: return redirect("/superadmin")
    if name.upper() == "OMEYI": return "Shop name cannot be Omeyi. Omeyi is platform name. <a href='/superadmin'>Go Back</a>"
    try:
        cur = conn.execute("INSERT INTO shops (name, admin_user, admin_pass) VALUES (?,?,?)",(name,au,generate_password_hash(ap))); sid = cur.lastrowid
        conn.execute("INSERT INTO users (shop_id, username, password, role, name, must_change, pwd_changed_at) VALUES (?,?,?,?,?,0,?)",(sid,au,generate_password_hash(ap),"owner",name,today_str())); conn.commit()
    except Exception: return f"Shop don exist. <a href='/superadmin'>Go Back</a>"
    return redirect("/superadmin")

@app.route("/superadmin-create-user", methods=["POST"])
def superadmin_create_user():
    if session.get('role') != 'superadmin': return blocked_msg()
    conn = get_db(); sid = int(request.form.get("shop_id") or 0); role = request.form.get("role"); u = request.form.get("username","").strip(); p = request.form.get("password","").strip(); nm = request.form.get("name")
    try:
        conn.execute("INSERT INTO users (shop_id, username, password, role, name, must_change, pwd_changed_at) VALUES (?,?,?,?,?,0,?)",(sid,u,generate_password_hash(p),role,nm,today_str()))
        if role == 'owner': conn.execute("UPDATE shops SET admin_user=?, admin_pass=? WHERE id=?",(u,generate_password_hash(p),sid))
        conn.commit()
    except: return "Username don exist. <a href='/superadmin'>Go Back</a>"
    return redirect("/superadmin")

@app.route("/edit-shop/<int:sid>", methods=["GET","POST"])
def edit_shop(sid):
    if session.get('role') != 'superadmin': return blocked_msg()
    conn = get_db()
    if request.method == "POST":
        if request.form.get("name","").strip().upper() == "OMEYI": return "Shop name cannot be Omeyi. <a href='/superadmin'>Go Back</a>"
        conn.execute("UPDATE shops SET name=?, admin_user=? WHERE id=?",(request.form.get("name"),request.form.get("admin_user"),sid)); conn.commit(); return redirect("/superadmin")
    s = conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone()
    return STYLE+top("Edit Shop","Super Admin")+f"""<div class="card"><form method="post"><label>Shop Name</label><input name="name" value="{s['name']}" required><label>MD Username</label><input name="admin_user" value="{s['admin_user']}" required><button>Save</button></form></div><a href='/superadmin'>Back</a>"""+end()

@app.route("/toggle-shop/<int:sid>")
def toggle_shop(sid):
    if session.get('role') != 'superadmin': return blocked_msg()
    conn = get_db(); s = conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone(); conn.execute("UPDATE shops SET is_active=? WHERE id=?",(0 if s["is_active"] else 1,sid)); conn.commit(); return redirect("/superadmin")

@app.route("/delete-shop/<int:sid>")
def delete_shop(sid):
    if session.get('role') != 'superadmin': return blocked_msg()
    conn = get_db(); conn.execute("DELETE FROM shops WHERE id=?",(sid,)); conn.execute("DELETE FROM users WHERE shop_id=?",(sid,)); conn.commit(); return redirect("/superadmin")

@app.route("/enter-shop/<int:sid>")
def enter_shop(sid):
    if session.get('role') != 'superadmin': return redirect("/")
    conn = get_db(); s = conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone()
    if not s: return redirect("/superadmin")
    session["view_shop_id"] = sid; session["view_shop_name"] = dict(s).get("name") or ""
    return redirect("/shop?view=1")

@app.route("/shop")
def shop():
    if 'role' not in session: return redirect("/")
    conn = get_db()
    if session.get('role') == 'superadmin':
        sid = session.get('view_shop_id') or 0; role = 'superadmin'; me = 'superadmin'
        if not sid: return redirect("/superadmin")
    else:
        sid = session.get('shop_id'); role = session.get('role'); me = session.get('username')
    period = request.args.get("period","all"); pstart = period_start(period)
    shop_rec = None
    try: shop_rec = conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone()
    except: pass
    staff_list = conn.execute("SELECT * FROM users WHERE shop_id=? AND role!='owner' ORDER BY id",(sid,)).fetchall() if sid else []
    sales_all = conn.execute("SELECT * FROM sales WHERE shop_id=?",(sid,)).fetchall(); purch = conn.execute("SELECT * FROM purchases WHERE shop_id=?",(sid,)).fetchall()
    sales = [s for s in sales_all if str(safe(s,'date') or '') >= pstart] if period != 'all' else sales_all
    sales_total = sum(float(safe(r,'total') or 0) for r in sales); purch_total = sum(float(safe(r,'total') or 0) for r in purch)
    gross_profit = sum((float(safe(r,'selling_price') or 0)-float(safe(r,'cost_price') or 0))*float(safe(r,'qty') or 0) for r in sales)
    total_losses = sum(float(safe(r,'amount') or 0) for r in conn.execute("SELECT * FROM losses WHERE shop_id=?",(sid,)).fetchall())
    total_exp = sum(float(safe(r,'amount') or 0) for r in conn.execute("SELECT * FROM expenses WHERE shop_id=?",(sid,)).fetchall())
    profit_loss = gross_profit - total_losses - total_exp
    debtors = conn.execute("SELECT * FROM debtors WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall(); creditors = conn.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall()
    expenses = conn.execute("SELECT * FROM expenses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); losses = conn.execute("SELECT * FROM losses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    requests_list = conn.execute("SELECT * FROM requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); submissions = conn.execute("SELECT * FROM submissions WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall(); alerts = conn.execute("SELECT * FROM alert_requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    items = {}
    for r in purch:
        it = r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":safe(r,'cost_price'),"selling_price":safe(r,'selling_price'),"expiry_date":safe(r,'expiry_date'),"min_stock":safe(r,'min_stock'),"max_stock":safe(r,'max_stock')}); items[it]["purch_qty"] += float(safe(r,'qty') or 0)
    for r in sales_all:
        it = r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":0,"selling_price":0,"expiry_date":"","min_stock":0,"max_stock":0}); items[it]["sales_qty"] += float(safe(r,'qty') or 0)
    combined = []
    for it,d in items.items():
        d["remaining"] = d["purch_qty"]-d["sales_qty"]; d["profit"] = (float(d["selling_price"] or 0)-float(d["cost_price"] or 0))*d["sales_qty"]
        d["status"] = "⛔ Out" if d["remaining"] <= 0 else ("⚠️ Low" if d["min_stock"] and d["remaining"] <= float(d["min_stock"]) else "✅ In Stock"); combined.append(d)
    stock_val_cost = sum(float(r["remaining"])*float(r["cost_price"] or 0) for r in combined); stock_val_sell = sum(float(r["remaining"])*float(r["selling_price"] or 0) for r in combined)
    opening_cost = purch_total; opening_sell = sum(float(safe(r,'qty') or 0)*float(safe(r,'selling_price') or 0) for r in purch)
    closing_cost = stock_val_cost; closing_sell = stock_val_sell
    perf = {}
    for r in sales:
        it = r["item"]; perf.setdefault(it,{"item":it,"qty":0,"profit":0,"total":0}); perf[it]["qty"] += float(safe(r,'qty') or 0); perf[it]["profit"] += (float(safe(r,'selling_price') or 0)-float(safe(r,'cost_price') or 0))*float(safe(r,'qty') or 0); perf[it]["total"] += float(safe(r,'total') or 0)
    perf_list = list(perf.values()); most_selling = sorted(perf_list, key=lambda x: x["qty"], reverse=True)[:5]
    auto_alerts = []
    for r in combined:
        if r["min_stock"] and r["remaining"] <= float(r["min_stock"]) and r["remaining"] > 0: auto_alerts.append(f"⚠️ LOW STOCK: {r['item']} — {r['remaining']} remain (Min {r['min_stock']}) — Expedited Action Needed")
        if r["remaining"] <= 0: auto_alerts.append(f"⛔ OUT OF STOCK: {r['item']} — 0 remain")
        if r["expiry_date"]:
            try:
                exp = datetime.date.fromisoformat(str(r["expiry_date"])[:10]); days = (exp-datetime.date.today()).days
                if 0 <= days <= 30: auto_alerts.append(f"⏰ EXPIRY ALERT: {r['item']} — Expires {r['expiry_date']} ({days} days left) — Expedited Action Needed")
                elif days < 0: auto_alerts.append(f"🚨 EXPIRED: {r['item']} — Expired {r['expiry_date']}")
            except: pass
    tl_opts = "".join([f"<option>{t}</option>" for t in TIMELINES]); dr_opts = "".join([f"<option>{t}</option>" for t in DEBTOR_REASONS]); lr_opts = "".join([f"<option>{t}</option>" for t in LOSS_REASONS])
    if role == 'sales':
        my_sales = [s for s in sales_all if s['created_by'] == me]; my_debt = [d for d in debtors if d['created_by'] == me]
        st = period_totals(my_sales); dt = period_totals(my_debt,'date')
        html = STYLE+top(f"Welcome, {session.get('name')} (Salesperson)",f"Shop ID {sid} • Today {today_str()} • Period: {period}")
        html += logout_bar()
        html += f"""<div class="section">📊 My Breakdown — Sales & Debtors Totals</div><div class="card"><table><tr><th>Period</th><th>My Sales Total</th><th>My Debtors Total</th></tr><tr><td>Today</td><td>{fmt(st['today'])}</td><td>{fmt(dt['today'])}</td></tr><tr><td>This Week</td><td>{fmt(st['week'])}</td><td>{fmt(dt['week'])}</td></tr><tr><td>This Month</td><td>{fmt(st['month'])}</td><td>{fmt(dt['month'])}</td></tr><tr><td>This Quarter</td><td>{fmt(st['quarter'])}</td><td>{fmt(dt['quarter'])}</td></tr><tr><td>This Year</td><td>{fmt(st['year'])}</td><td>{fmt(dt['year'])}</td></tr></table></div>"""
        html += "<div class='section'>📦 Inventory / Stock List — With Cost + Selling Price</div><div class='card'><table><tr><th>Item</th><th>Qty In Stock</th><th>Cost Price</th><th>Selling Price</th><th>Status</th></tr>"
        for r in combined: html += f"<tr><td><b>{r['item']}</b></td><td>{r['remaining']}</td><td>{fmt(r['cost_price'])}</td><td>{fmt(r['selling_price'])}</td><td>{r['status']}</td></tr>"
        html += "</table></div>"
        opts = "".join([f"<option value='{r['item']}'>{r['item']} - Available {r['remaining']}</option>" for r in combined if r['remaining'] > 0])
        html += f"""<div class="section">🛒 My Sales — Add Sale</div><div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{opts}</select><div class="grid2"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price (₦) Per One</label><input name="price" type="number" step="any" required></div></div><label>Or new item</label><input name="item_new"><button class="green">ADD SALE</button></form></div>"""
        html += f"<div class='section'>👥 My Debtors — See & Settle Full / Partial + Timeline</div><div class='card'><form method='post' action='/add_debtor'><label>Customer Name</label><input name='name' required><label>Amount (₦)</label><input name='amount' type='number' step='any' required><label>Phone</label><input name='phone'><label>Item</label><input name='item'><label>Reason For Debtor</label><select name='reason'>{dr_opts}</select><label>Settlement Timeline</label><select name='timeframe'>{tl_opts}</select><button>Add Debtor</button></form><hr>"
        for r in my_debt:
            bal = float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            html += f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)} - {r['status']} - {r['item']} - Reason: {r['reason']} - Timeline: {r['timeframe']}</div><a href='/settle_debtor_form/{r['id']}'><button class='small green'>Settle</button></a></div>"
        html += "</div>"
        html += "<div class='section'>🧾 My Sales Records</div><div class='card'><table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th></tr>"
        for r in my_sales: html += f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td></tr>"
        html += "</table></div>"
        return html+logout_bar()+end()
    html = STYLE+top(f"Welcome, {session.get('name')} ({display_role(role)})",f"Shop {shop_rec['name'] if shop_rec else sid} • Today {today_str()} • Period: {period} • {'VIEWING AS SUPER ADMIN - Role stays Super Admin' if role=='superadmin' else ''}")
    html += logout_bar()
    if role == 'superadmin' and shop_rec:
        html += f"""<div class="card" style="border:2px solid #dc2626"><b>👁️ SUPER ADMIN VIEWING SHOP - You are still Super Admin, NOT MD/CEO</b><br><a href='/superadmin'><button class='blue'>Back to Super Admin</button></a></div>"""
    if role == 'owner' and shop_rec:
        html += f"""<div class="card" style="border:2px solid #0b3d91"><div class="section" style="margin:0 0 10px">👑 MD/CEO Details — View Only</div><table><tr><th>Name</th><td><b>{shop_rec['name']}</b></td></tr><tr><th>MD Username</th><td>{shop_rec['admin_user']}</td></tr></table></div>"""
    if role == 'owner':
        html += "<div class='section'>👥 Staff List + Performance — MD ONLY (MD Off The List)</div><div class='card'><table><tr><th>Name</th><th>Designation</th><th>Username</th><th>Performance</th></tr>"
        for u in staff_list:
            sc = sum(1 for s in sales_all if s['created_by'] == u['username']); pc = sum(1 for s in purch if s['created_by'] == u['username']); rc = sum(1 for s in requests_list if s['created_by'] == u['username'])
            html += f"<tr><td><b>{u['name']}</b></td><td>{display_role(u['role'])}</td><td>{u['username']}</td><td>{sc} sales / {pc} purch / {rc} req</td></tr>"
        html += "</table><p class='muted'>Only Super Admin creates staff. MD only can view this list.</p></div>"
    if role in ['owner','manager','superadmin']:
        html += f"""<div class="card"><b>📊 Dashboard Totals — MD & Manager</b><table><tr><th>Total Stock Value (Cost)</th><td>{fmt(stock_val_cost)}</td></tr><tr><th>Total Stock Value (Selling)</th><td>{fmt(stock_val_sell)}</td></tr><tr><th>Total Sales Value (Period)</th><td>{fmt(sales_total)}</td></tr><tr><th>Total Purchases Value</th><td>{fmt(purch_total)}</td></tr><tr><th>Gross Profit Value</th><td>{fmt(gross_profit)}</td></tr><tr><th>Total Losses</th><td>{fmt(total_losses)}</td></tr><tr><th>Total Expenses</th><td>{fmt(total_exp)}</td></tr><tr><th>Profit / Loss</th><td><b>{fmt(profit_loss)}</b></td></tr></table></div>"""
    if role in ['owner','superadmin']:
        html += f"""<div class="card"><b>📦 Opening & Closing Stock Value — MD ONLY</b><table><tr><th>Opening Stock Value (Cost)</th><td>{fmt(opening_cost)}</td></tr><tr><th>Opening Stock Value (Selling)</th><td>{fmt(opening_sell)}</td></tr><tr><th>Closing Stock Value (Cost) = Current Stock</th><td>{fmt(closing_cost)}</td></tr><tr><th>Closing Stock Value (Selling)</th><td>{fmt(closing_sell)}</td></tr></table><p class='muted'>Closing = Current Stock - All Sales for Period. Closing today automatically becomes Opening tomorrow.</p></div>"""
    html += f"""<div class='section'>🏆 Performance Report — Period: {period.upper()}</div><div class='card'><form method='get' action='/shop'><label>Choose Period</label><select name='period' onchange='this.form.submit()'><option value='all' {'selected' if period=='all' else ''}>All Time</option><option value='today' {'selected' if period=='today' else ''}>Today</option><option value='week' {'selected' if period=='week' else ''}>This Week</option><option value='month' {'selected' if period=='month' else ''}>This Month</option><option value='quarter' {'selected' if period=='quarter' else ''}>This Quarter</option><option value='year' {'selected' if period=='year' else ''}>This Year</option></select></form><p class='muted'>Period Lock: Old period records no go show for current period unless you call am with Period Filter.</p></div>"""
    if role in ['owner','superadmin']:
        total_perf = sum(x["total"] for x in perf_list) or 1; colors = ["#0b3d91","#0ea5e9","#16a34a","#f59e0b","#dc2626"]; segs = []; start = 0
        for i,x in enumerate(most_selling):
            pct = x["total"]/total_perf*100; segs.append(f"{colors[i%len(colors)]} {start:.1f}% {start+pct:.1f}%"); start += pct
        grad = f"conic-gradient({', '.join(segs)})" if segs else "conic-gradient(#e2e8f0 0% 100%)"
        legend = "".join([f"<div><span style='display:inline-block;width:12px;height:12px;background:{colors[i%len(colors)]}'></span> {x['item']} — {fmt(x['total'])} ({x['total']/total_perf*100:.1f}%)</div>" for i,x in enumerate(most_selling)])
        html += f"""<div class='section'>📊 Pie Chart — Performance — MD ONLY</div><div class='card' style='text-align:center'><div class='pie' style='background:{grad}'></div><br>{legend or 'No sales yet'}</div>"""
    html += "<div class='section'>📦 Stock / Inventory</div><div class='card'><table><tr><th>Item</th><th>Purchased</th><th>Sold</th><th>Remaining</th><th>Cost</th><th>Selling</th><th>Expiry</th><th>Status</th></tr>"
    for r in combined: html += f"<tr><td><b>{r['item']}</b></td><td>{r['purch_qty']}</td><td>{r['sales_qty']}</td><td><b>{r['remaining']}</b></td><td>{fmt(r['cost_price'])}</td><td>{fmt(r['selling_price'])}</td><td>{r['expiry_date'] or '-'}</td><td>{r['status']}</td></tr>"
    html += "</table></div>"
    if role == 'admin':
        opts = "".join([f"<option value='{r['item']}'>{r['item']} - Available {r['remaining']}</option>" for r in combined if r['remaining'] > 0])
        html += f"""<div class="section">🛒 Add Sale - Admin Only</div><div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{opts}</select><div class="grid2"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price</label><input name="price" type="number" step="any" required></div></div><button class="green">ADD SALE</button></form></div>"""
    if role in ['manager','admin']:
        html += f"""<div class="section">➕ Add Purchase - Manager/Admin Only</div><div class="card"><form method="post" action="/add_purchase"><label>Item Name</label><input name="item" required><div class="grid3"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Cost Price</label><input name="cost_price" type="number" step="any" required></div><div><label>Selling Price</label><input name="selling_price" type="number" step="any" required></div></div><div class="grid3"><div><label>Expiry Date</label><input name="expiry_date" type="date"></div><div><label>Min Stock</label><input name="min_stock" type="number" step="any"></div><div><label>Max Stock</label><input name="max_stock" type="number" step="any"></div></div><button>Add Purchase</button></form></div>"""
    if role in ['manager','admin','owner','superadmin']:
        html += "<div class='section'>👥 Debtors — MD View Only</div><div class='card'>"
        if role == 'admin': html += f"""<form method="post" action="/add_debtor_admin"><label>Customer Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item</label><input name="item"><label>Reason</label><select name="reason">{dr_opts}</select><label>Timeline</label><select name="timeframe">{tl_opts}</select><button>Add Debtor</button></form><hr>"""
        for r in debtors:
            bal = float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            btn = f"<a href='/settle_debtor_form/{r['id']}'><button class='small green'>Settle Full / Partial</button></a>" if role in ['admin','sales'] else "<span class='muted'>View Only</span>"
            html += f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Bal {fmt(bal)} - {r['status']} - Reason: {r['reason']} - Timeline: {r['timeframe']}</div>{btn}</div>"
        html += "</div>"
    if role in ['manager','admin','owner','superadmin']:
        html += "<div class='section'>🏦 Creditors — MD View Only, Manager + Admin Can Settle Full / Partial</div><div class='card'>"
        if role in ['manager','admin']: html += f"""<form method="post" action="/add_creditor"><label>Creditor Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item</label><input name="item"><label>Timeline</label><select name="timeframe">{tl_opts}</select><button>Add Creditor</button></form><hr>"""
        for r in creditors:
            bal = float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            btn = f"<a href='/settle_creditor_form/{r['id']}'><button class='small'>Settle Full / Partial</button></a>" if role in ['manager','admin'] else "<span class='muted'>View Only</span>"
            html += f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Bal {fmt(bal)} - {r['status']} - Timeline: {r['timeframe']}</div>{btn}</div>"
        html += "</div>"
    if role in ['manager','admin','owner','superadmin']:
        html += "<div class='section'>💸 Losses & Expenses</div><div class='card'>"
        if role in ['manager','admin']: html += f"<form method='post' action='/add_loss'><label>Loss Item</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Reason For Loss</label><select name='reason'>{lr_opts}</select><button>Add Loss</button></form><hr>"
        if role == 'admin': html += "<form method='post' action='/add_expense'><label>Expense Item (Admin Direct)</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Note</label><input name='note'><button>Add Expense</button></form><hr>"
        for r in expenses: html += f"<div class='row-card'><div><b>Expense: {r['item']}</b> - {r['note']}</div><b>{fmt(r['amount'])}</b></div>"
        for r in losses: html += f"<div class='row-card'><div><b>Loss: {r['item']}</b> - Reason: {r['reason']}</div><b>{fmt(r['amount'])}</b></div>"
        html += "</div>"
    if role in ['manager','admin','owner','superadmin']:
        html += "<div class='section'>📩 Requests To MD/CEO</div><div class='card'>"
        if role in ['manager','admin']: html += "<form method='post' action='/add_request'><label>Type</label><select name='type'><option>Expenditure</option><option>Budget Request</option><option>Salary Schedule</option><option>Expense Request</option></select><label>Title</label><input name='title' required><label>Amount</label><input name='amount' type='number' step='any'><label>Note</label><input name='note'><button>Send Request</button></form><hr>"
        for r in requests_list:
            md_form = ""
            if role == 'owner' and r['status'] == 'Pending': md_form = f"""<form method="post" action="/md_remark/{r['id']}" style="margin-top:8px"><label>MD Remark — Approve</label><textarea name="remark" required></textarea><button class="small green">Approve</button></form>"""
            html += f"<div class='row-card'><div><b>{r['type']}: {r['title']}</b> - {r['status']}<br><span class='muted'>{fmt(r['amount'])}</span><br><b>Note:</b> {r['note']}<br>{('<b>MD Remark:</b> '+r['owner_feedback']) if r['owner_feedback'] else ''}{md_form}</div></div>"
        html += "</div>"
        html += "<div class='section'>🚨 Alerts — Expiry + Stock Levels + Expedited</div><div class='card'>"
        if auto_alerts: html += "<div style='background:#fef3c7;padding:12px;border-radius:10px;margin-bottom:10px'><b>🔔 Auto Alerts:</b><br>"+"<br>".join(auto_alerts)+"</div>"
        if role in ['manager','admin']: html += "<form method='post' action='/add_alert'><label>Alert Item</label><input name='alert_item' required><label>Alert Type</label><select name='alert_type'><option>Low Stock</option><option>Expiry</option><option>Other</option></select><label>Message</label><input name='manager_message'><button>Send Alert</button></form><hr>"
        html += "<table><tr><th>Item</th><th>Type</th><th>Message</th><th>Status</th><th>MD Remark</th></tr>"
        for r in alerts: html += f"<tr><td><b>{r['alert_item']}</b></td><td>{r['alert_type']}</td><td>{r['manager_message']}</td><td>{r['status']}</td><td>{r['owner_remark'] or '-'}</td></tr>"
        html += "</table></div>"
    if role in ['manager','admin','owner','superadmin']:
        html += "<div class='section'>📋 Submitted History For Review — Daily / Weekly / Monthly / Quarterly / Yearly</div><div class='card'>"
        if role in ['manager','admin']: html += "<form method='post' action='/submit_history'><label>Period</label><select name='period'><option>Daily</option><option>Weekly</option><option>Monthly</option><option>Quarterly</option><option>Yearly</option></select><label>Period Label</label><input name='period_label' placeholder='e.g 2026-11-25' required><label>Summary</label><textarea name='summary'></textarea><label>Manager Remark</label><input name='manager_remark'><button>Submit History</button></form><hr>"
        for s in submissions:
            md_form = ""
            if role == 'owner' and s['status'] == 'Submitted': md_form = f"""<form method="post" action="/md_submission_remark/{s['id']}" style="margin-top:8px"><label>MD Remark — Approve / Validate</label><textarea name="remark" required></textarea><button class="small green">Approve</button></form>"""
            html += f"<div class='row-card'><div><b>{s['period']} — {s['period_label']} - {s['status']}</b><br><span class='muted'>{s['summary']} • {s['date']}</span><br><b>Manager Remark:</b> {s['manager_remark']}<br>{('<b>MD Remark:</b> '+s['owner_remark']) if s['owner_remark'] else ''}{md_form}</div></div>"
        html += "</div>"
    return html+logout_bar()+end()

@app.route("/add_user", methods=["POST"])
def add_user(): return blocked_msg("Only Super Admin fit create staff.")

@app.route("/sell", methods=["POST"])
def sell():
    if session.get('role') not in ['sales','admin','manager']: return blocked_msg("Only Sales/Admin fit sell.")
    conn = get_db(); sid = session.get('shop_id')
    item = request.form.get("item") or request.form.get("item_new","")
    try: qty = float(request.form.get("qty") or 0); price = float(request.form.get("price") or 0)
    except: return "Invalid qty/price <a href='/shop'>Go Back</a>"
    if not item or qty <= 0: return "Fill item & qty <a href='/shop'>Go Back</a>"
    p = conn.execute("SELECT COALESCE(SUM(qty),0) as q FROM purchases WHERE shop_id=? AND item=?",(sid,item)).fetchone(); s = conn.execute("SELECT COALESCE(SUM(qty),0) as q FROM sales WHERE shop_id=? AND item=?",(sid,item)).fetchone()
    remain = float(safe(p,'q'))-float(safe(s,'q'))
    if remain <= 0: return STYLE+top("Out of Stock","")+f"<div class='card'><h3>⛔ OUT OF STOCK</h3><p>{item} don finish.</p><a href='/shop'>Go Back</a></div>"+end()
    if qty > remain: return STYLE+top("Not Enough Stock","")+f"<div class='card'><h3>⛔ NOT ENOUGH</h3><p>Only {remain} remain.</p><a href='/shop'>Go Back</a></div>"+end()
    last = conn.execute("SELECT * FROM purchases WHERE shop_id=? AND item=? ORDER BY id DESC LIMIT 1",(sid,item)).fetchone()
    cp = float(safe(last,'cost_price') or 0) if last else 0; sp = price; total = qty*price
    conn.execute("INSERT INTO sales (shop_id, item, qty, price, cost_price, selling_price, total, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(sid,item,qty,price,cp,sp,total,session.get('username'),session.get('role'),today_str())); conn.commit()
    return STYLE+top("Sale Added","")+f"<div class='card'><h3>✅ Sale Added: {item} x{qty} = {fmt(total)}</h3><a href='/shop'>Go Back</a></div>"+end()

@app.route("/add_purchase", methods=["POST"])
def add_purchase():
    if session.get('role') not in ['manager','admin']: return blocked_msg("MD cannot add purchase.")
    conn = get_db(); qty = float(request.form.get("qty") or 0); cp = float(request.form.get("cost_price") or 0); sp = float(request.form.get("selling_price") or 0)
    conn.execute("INSERT INTO purchases (shop_id, item, qty, price, cost_price, selling_price, total, expiry_date, min_stock, max_stock, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),qty,cp,cp,sp,qty*cp,request.form.get("expiry_date",""),float(request.form.get("min_stock") or 0),float(request.form.get("max_stock") or 0),session.get('username'),session.get('role'),today_str())); conn.commit()
    return redirect("/shop")

@app.route("/add_debtor", methods=["POST"])
def add_debtor():
    if session.get('role') != 'sales': return blocked_msg("Only Salesperson fit add debtor.")
    conn = get_db(); conn.execute("INSERT INTO debtors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("reason",""),"Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/add_debtor_admin", methods=["POST"])
def add_debtor_admin():
    if session.get('role') != 'admin': return blocked_msg("Only Admin.")
    conn = get_db(); conn.execute("INSERT INTO debtors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("reason",""),"Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/settle_debtor_form/<int:did>", methods=["GET","POST"])
def settle_debtor_form(did):
    if session.get('role') not in ['sales','admin']: return blocked_msg("Only Sales/Admin fit settle Debtors.")
    conn = get_db(); r = conn.execute("SELECT * FROM debtors WHERE id=? AND shop_id=?",(did,session.get('shop_id'))).fetchone()
    if not r: return "Debtor not found"
    bal = float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
    if request.method == "POST":
        amt = float(request.form.get("amount") or 0)
        if amt <= 0 or amt > bal: return f"Amount must be 1 to {bal}. <a href='/shop'>Go Back</a>"
        new_paid = float(safe(r,'paid_amount') or 0)+amt; status = 'Paid' if new_paid >= float(safe(r,'amount') or 0)-0.01 else 'Partially Paid'
        conn.execute("UPDATE debtors SET paid_amount=?, status=? WHERE id=?",(new_paid,status,did)); conn.commit(); return redirect("/shop")
    return STYLE+top("Settle Debtor — Full / Partial","")+f"""<div class="card"><p><b>{r['name']}</b> — Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)}</p><form method="post"><label>Amount To Pay Now</label><input name="amount" type="number" step="any" max="{bal}" required><button class="green">Settle Now</button></form></div>"""+end()

@app.route("/add_creditor", methods=["POST"])
def add_creditor():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit add creditor.")
    conn = get_db(); conn.execute("INSERT INTO creditors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),"", "Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/settle_creditor_form/<int:cid>", methods=["GET","POST"])
def settle_creditor_form(cid):
    if session.get('role') not in ['manager','admin']: return blocked_msg("MD cannot settle Creditors. Only Manager & Admin.")
    conn = get_db(); r = conn.execute("SELECT * FROM creditors WHERE id=? AND shop_id=?",(cid,session.get('shop_id'))).fetchone()
    if not r: return "Creditor not found"
    bal = float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
    if request.method == "POST":
        amt = float(request.form.get("amount") or 0)
        if amt <= 0 or amt > bal: return f"Amount must be 1 to {bal}. <a href='/shop'>Go Back</a>"
        new_paid = float(safe(r,'paid_amount') or 0)+amt; status = 'Paid' if new_paid >= float(safe(r,'amount') or 0)-0.01 else 'Partially Paid'
        conn.execute("UPDATE creditors SET paid_amount=?, status=? WHERE id=?",(new_paid,status,cid)); conn.commit(); return redirect("/shop")
    return STYLE+top("Settle Creditor — Full / Partial","")+f"""<div class="card"><p><b>{r['name']}</b> — Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)} | Timeline {r['timeframe']}</p><form method="post"><label>Amount To Pay Now</label><input name="amount" type="number" step="any" max="{bal}" required><button class="green">Settle Now</button></form></div>"""+end()

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if session.get('role') != 'admin': return blocked_msg("Only Admin direct.")
    conn = get_db(); conn.execute("INSERT INTO expenses (shop_id, item, amount, note, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("note",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/add_loss", methods=["POST"])
def add_loss():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit add loss.")
    conn = get_db(); conn.execute("INSERT INTO losses (shop_id, item, amount, note, reason, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("reason",""),request.form.get("reason",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/add_request", methods=["POST"])
def add_request():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit send request.")
    conn = get_db(); conn.execute("INSERT INTO requests (shop_id, type, title, amount, note, items, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("type"),request.form.get("title"),float(request.form.get("amount") or 0),request.form.get("note",""),"", "Pending",session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/md_remark/<int:rid>", methods=["POST"])
def md_remark(rid):
    if session.get('role') != 'owner': return blocked_msg("Only MD.")
    conn = get_db(); conn.execute("UPDATE requests SET owner_feedback=?, status='Approved' WHERE id=? AND shop_id=?",(request.form.get("remark",""),rid,session.get('shop_id'))); conn.commit(); return redirect("/shop")

@app.route("/add_alert", methods=["POST"])
def add_alert():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin.")
    conn = get_db(); conn.execute("INSERT INTO alert_requests (shop_id, alert_item, alert_type, manager_message, status, created_by, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("alert_item"),request.form.get("alert_type"),request.form.get("manager_message",""),"Pending",session.get('username'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/submit_history", methods=["POST"])
def submit_history():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin.")
    conn = get_db(); conn.execute("INSERT INTO submissions (shop_id, period, period_label, summary, status, manager_remark, created_by, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("period"),request.form.get("period_label"),request.form.get("summary",""),"Submitted",request.form.get("manager_remark",""),session.get('username'),today_str())); conn.commit(); return redirect("/shop")

@app.route("/md_submission_remark/<int:sid2>", methods=["POST"])
def md_submission_remark(sid2):
    if session.get('role') != 'owner': return blocked_msg("Only MD.")
    conn = get_db(); conn.execute("UPDATE submissions SET owner_remark=?, status='Approved' WHERE id=? AND shop_id=?",(request.form.get("remark",""),sid2,session.get('shop_id'))); conn.commit(); return redirect("/shop")

@app.route("/subscription")
def subscription():
    if 'role' not in session: return redirect("/")
    return STYLE+top("Subscription","Pay to continue")+f"""<div class="card"><b>How to pay:</b><br>1. Transfer to {PAYMENT_BANK} <b>{PAYMENT_ACCOUNT}</b> ({PAYMENT_NAME})<br>2. Click I Don Pay<br><a href="/shop">Go Back</a></div>"""+end()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

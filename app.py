from flask import Flask, request, redirect, session, render_template_string
import datetime, os, sqlite3, urllib.parse
try:
    import psycopg2, psycopg2.extras
except: psycopg2 = None

app = Flask(__name__)
app.secret_key = "omeyi-secret-key"
DATABASE_URL = os.environ.get("DATABASE_URL")
DB = "shop.db"

# ===== OMEYI CONFIG =====
APP_URL = "https://omeyi.onrender.com"
PAYMENT_BANK = "Opay"
PAYMENT_ACCOUNT = "8037372296"
PAYMENT_NAME = "Joseph George"
PRICE_NOTICE = "(Prices may be reviewed at any time)"
DEFAULT_PLANS = [{"name":"Monthly","amount":5000,"days":30},{"name":"Quarterly","amount":13000,"days":90},{"name":"Yearly","amount":45000,"days":365}]
# =========================

class PGWrapper:
    def __init__(self, conn): self.conn = conn
    def cursor(self): return PGCursor(self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))
    def commit(self): return self.conn.commit()
    def close(self): return self.conn.close()
    def execute(self, sql, params=()):
        cur=self.cursor(); cur.execute(sql, params); return cur
class PGCursor:
    def __init__(self, cur): self.cur=cur
    def execute(self, sql, params=()):
        sql=sql.replace("?","%s").replace("INTEGER PRIMARY KEY","SERIAL PRIMARY KEY")
        return self.cur.execute(sql, params)
    def fetchone(self): return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()
    def close(self): return self.cur.close()

def get_db():
    if DATABASE_URL and psycopg2:
        c=psycopg2.connect(DATABASE_URL, sslmode='require'); c.autocommit=True; return PGWrapper(c)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def safe(row,*names):
    d=dict(row) if row is not None else {}
    for n in names:
        if n in d and d[n] is not None: return d[n]
    return 0
def today_str(): return datetime.date.today().isoformat()
def display_role(r): return {'owner':'MD/CEO','manager':'Manager','sales':'Salesperson','admin':'Admin','superadmin':'Super Admin'}.get(r,r or '')
def fmt(n):
    try: return f"₦{float(n or 0):,.0f}"
    except: return "₦0"

def get_plans():
    conn=get_db()
    try:
        rows=conn.execute("SELECT name, amount, days FROM subscription_plans ORDER BY days").fetchall()
        if rows: return [{"name":r["name"],"amount":float(r["amount"]),"days":int(r["days"])} for r in rows]
    except: pass
    return DEFAULT_PLANS

def stock_remaining(sid, item):
    conn=get_db()
    p=conn.execute("SELECT COALESCE(SUM(qty),0) as q FROM purchases WHERE shop_id=? AND item=?",(sid,item)).fetchone()
    s=conn.execute("SELECT COALESCE(SUM(qty),0) as q FROM sales WHERE shop_id=? AND item=?",(sid,item)).fetchone()
    return float(safe(p,'q'))-float(safe(s,'q'))

def wa_link(phone,msg):
    phone="".join([c for c in str(phone or "") if c.isdigit()])
    if phone.startswith("0"): phone="234"+phone[1:]
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"

def shop_contacts(sid):
    conn=get_db()
    try:
        r=conn.execute("SELECT md_phone, manager_phone FROM shop_settings WHERE shop_id=?",(sid,)).fetchone()
        if r: return dict(r)
    except: pass
    return {"md_phone":"","manager_phone":""}

# Postgres-safe upsert
def upsert_settings(sid, md, mg):
    conn=get_db()
    try:
        conn.execute("INSERT INTO shop_settings (shop_id, md_phone, manager_phone) VALUES (?,?,?)",(sid,md,mg))
    except:
        conn.execute("UPDATE shop_settings SET md_phone=?, manager_phone=? WHERE shop_id=?",(md,mg,sid))
    conn.commit()

def init_db():
    conn=get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY, name TEXT, admin_user TEXT, admin_pass TEXT, is_active INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, shop_id INTEGER, username TEXT UNIQUE, password TEXT, role TEXT, name TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, qty REAL, price REAL, cost_price REAL DEFAULT 0, selling_price REAL DEFAULT 0, total REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, qty REAL, price REAL, cost_price REAL DEFAULT 0, selling_price REAL DEFAULT 0, total REAL DEFAULT 0, expiry_date TEXT DEFAULT '', min_stock REAL DEFAULT 0, max_stock REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS debtors (id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, amount REAL, phone TEXT DEFAULT '', item TEXT DEFAULT '', reason TEXT DEFAULT '', status TEXT DEFAULT 'Owing', timeframe TEXT DEFAULT '', paid_amount REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS creditors (id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, amount REAL, phone TEXT DEFAULT '', item TEXT DEFAULT '', reason TEXT DEFAULT '', status TEXT DEFAULT 'Owing', timeframe TEXT DEFAULT '', paid_amount REAL DEFAULT 0, created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS losses (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, amount REAL, note TEXT DEFAULT '', reason TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY, shop_id INTEGER, item TEXT, amount REAL, note TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, shop_id INTEGER, type TEXT, title TEXT, amount REAL DEFAULT 0, note TEXT DEFAULT '', items TEXT DEFAULT '', status TEXT DEFAULT 'Pending', owner_feedback TEXT DEFAULT '', created_by TEXT DEFAULT '', created_by_role TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, shop_id INTEGER, period TEXT, period_label TEXT, summary TEXT DEFAULT '', status TEXT DEFAULT 'Submitted', manager_remark TEXT DEFAULT '', owner_remark TEXT DEFAULT '', created_by TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS alert_requests (id INTEGER PRIMARY KEY, shop_id INTEGER, alert_item TEXT DEFAULT '', alert_type TEXT DEFAULT '', manager_message TEXT DEFAULT '', status TEXT DEFAULT 'Pending', owner_remark TEXT DEFAULT '', created_by TEXT DEFAULT '', date TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS shop_settings (shop_id INTEGER PRIMARY KEY, md_phone TEXT DEFAULT '', manager_phone TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS subscription_plans (name TEXT, amount REAL, days INTEGER)")
    for tbl in ["sales","purchases","debtors","creditors","losses","expenses","requests","submissions","alert_requests"]:
        for col in ["created_by TEXT DEFAULT ''","created_by_role TEXT DEFAULT ''","date TEXT DEFAULT ''","cost_price REAL DEFAULT 0","selling_price REAL DEFAULT 0","total REAL DEFAULT 0","phone TEXT DEFAULT ''","item TEXT DEFAULT ''","note TEXT DEFAULT ''","name TEXT DEFAULT ''","amount REAL DEFAULT 0","reason TEXT DEFAULT ''","status TEXT DEFAULT 'Owing'","title TEXT DEFAULT ''","type TEXT DEFAULT ''","timeframe TEXT DEFAULT ''","paid_amount REAL DEFAULT 0","items TEXT DEFAULT ''","owner_feedback TEXT DEFAULT ''","expiry_date TEXT DEFAULT ''","min_stock REAL DEFAULT 0","max_stock REAL DEFAULT 0","period TEXT DEFAULT ''","period_label TEXT DEFAULT ''","summary TEXT DEFAULT ''","manager_remark TEXT DEFAULT ''","owner_remark TEXT DEFAULT ''","alert_item TEXT DEFAULT ''","alert_type TEXT DEFAULT ''","manager_message TEXT DEFAULT ''"]:
            try: conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
            except: pass
    conn.commit(); conn.close()
init_db()

def blocked_msg(m="You are not allowed to post this."): return f"{m} <a href='/shop'>Go Back</a>"
STYLE="""<style>*{box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#eaf0f7;color:#1e293b;padding-bottom:40px}.top{background:linear-gradient(135deg,#0b3d91,#0b5ed7 55%,#0ea5e9);color:#fff;padding:18px 16px;border-bottom:4px solid #f59e0b}.top a{color:#fde68a;font-weight:700}.omeyi{font-size:12px;color:#bfdbfe;margin:0;letter-spacing:3px;text-transform:uppercase;font-weight:800}h1{font-size:24px;margin:6px 0 2px}.sub{color:#dbeafe;font-size:13px;margin:0}.wrap{padding:0 12px 30px;max-width:960px;margin:auto}.card{background:#fff;padding:16px;border-radius:16px;margin-bottom:14px;box-shadow:0 4px 14px rgba(11,61,145,.10);border:1px solid #dbeafe}label{font-size:12px;font-weight:800;color:#0b3d91;text-transform:uppercase}input,select,textarea{padding:12px;margin:6px 0 11px;width:100%;border:1.5px solid #cbd5e1;border-radius:10px;font-size:14px;background:#f8fafc}button{padding:13px;background:#0b3d91;color:#fff;border:none;border-radius:11px;cursor:pointer;width:100%;font-weight:800}button.green{background:#16a34a}button.orange{background:#ea580c}button.blue{background:#0b5ed7}button.small{padding:8px 11px;width:auto;font-size:12px}table{width:100%;border-collapse:collapse}th{background:#0b3d91;color:#fff;padding:11px 8px;font-size:11px;text-align:left}td{padding:11px 8px;font-size:13px;border-bottom:1px solid #e2e8f0}.section{font-size:18px;font-weight:900;margin:20px 2px 10px;color:#0b3d91}.muted{font-size:12px;color:#64748b}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.footer{text-align:center;color:#64748b;font-size:12px;padding:18px 0}.badge{font-size:11px;background:#fef3c7;padding:5px 10px;border-radius:20px;font-weight:800}.row-card{background:#fff;padding:13px;border-radius:12px;margin-bottom:9px;display:flex;justify-content:space-between;border-left:6px solid #0b5ed7}</style>"""
FOOTER='<div class="footer">© Omeyi • All Rights Reserved • Powered by Omeyi Blue</div>'
QR_IMG=f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={APP_URL}"
def top(t,s=""): return f'<div class="top"><p class="omeyi">Omeyi</p><h1>{t}</h1><p class="sub">{s}</p></div><div class="wrap" style="margin-top:16px">'
def end(): return "</div>"+FOOTER

# ---------- LOGIN ----------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","").strip(); conn=get_db()
        if u=="superadmin" and p=="omeyi123":
            session.update(role="superadmin",username="superadmin",shop_id=0,name="Super Admin"); return redirect("/superadmin")
        r=conn.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p)).fetchone()
        if r: session.update(role=r["role"],username=r["username"],shop_id=r["shop_id"],name=r["name"]); return redirect("/shop")
        s=conn.execute("SELECT * FROM shops WHERE admin_user=? AND admin_pass=?",(u,p)).fetchone()
        if s: session.update(role="owner",username=u,shop_id=s["id"],name=s["name"]); return redirect("/shop")
        return STYLE+top("Login","Wrong username or password")+"<div class='card'><p>Wrong login. <a href='/'>Try again</a></p></div>"+end()
    return STYLE+top("Login","Welcome back - Manage your shop with confidence")+f"""<div class="card" style="text-align:center"><img src="{QR_IMG}" style="width:150px;border-radius:12px;border:6px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.15)"><p><b>Scan to open Omeyi</b><br><span class="muted">{APP_URL}</span></p></div><div class="card"><form method="post"><label>Username</label><input name="username" required><label>Password</label><input name="password" type="password" required><button>LOGIN</button></form></div><div class="card"><b>New Shop?</b> <a href="/subscription">View Subscription Plans</a><br><span class="muted">Pay to {PAYMENT_BANK} {PAYMENT_ACCOUNT} ({PAYMENT_NAME}) - {PRICE_NOTICE}</span></div>"""+end()
@app.route("/logout")
def logout(): session.clear(); return redirect("/")

# ---------- SUPER ADMIN ----------
@app.route("/superadmin")
def superadmin():
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); shops=conn.execute("SELECT * FROM shops ORDER BY id DESC").fetchall()
    rows="".join([f"<tr><td>{s['name']}</td><td>{s['admin_user']}</td><td>{'Active' if s['is_active'] else 'Suspended'}</td><td><a href='/toggle-shop/{s['id']}'>Toggle</a></td></tr>" for s in shops])
    return STYLE+top("Super Admin","All Shops")+f"""<div class="card"><form method="post" action="/create-shop"><label>Shop Name</label><input name="name" required><label>Admin Username</label><input name="admin_user" required><label>Admin Password</label><input name="admin_pass" required><button>Create Shop</button></form></div><div class="card"><table><tr><th>Shop</th><th>Admin</th><th>Status</th><th>Action</th></tr>{rows}</table></div><div class="card"><a href="/shop-settings"><button class="blue">⚙️ Edit Subscription Prices (Adjustable Anytime)</button></a><br><span class="muted">{PRICE_NOTICE}</span></div><a href="/logout">Logout</a>"""+end()
@app.route("/create-shop", methods=["POST"])
def create_shop():
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO shops (name, admin_user, admin_pass) VALUES (?,?,?)",(request.form.get("name"),request.form.get("admin_user"),request.form.get("admin_pass"))); conn.commit(); return redirect("/superadmin")
@app.route("/toggle-shop/<int:sid>")
def toggle_shop(sid):
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); s=conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone(); conn.execute("UPDATE shops SET is_active=? WHERE id=?",(0 if s["is_active"] else 1,sid)); conn.commit(); return redirect("/superadmin")

# ---------- SHOP ----------
@app.route("/shop")
def shop():
    if 'role' not in session: return redirect("/")
    conn=get_db(); sid=session.get('shop_id'); role=session.get('role')
    sales=conn.execute("SELECT * FROM sales WHERE shop_id=?",(sid,)).fetchall(); purch=conn.execute("SELECT * FROM purchases WHERE shop_id=?",(sid,)).fetchall()
    sales_total=sum(float(safe(r,'total') or 0) for r in sales); purch_total=sum(float(safe(r,'total') or 0) for r in purch); profit=sum((float(safe(r,'selling_price') or 0)-float(safe(r,'cost_price') or 0))*float(safe(r,'qty') or 0) for r in sales)
    debtors=conn.execute("SELECT * FROM debtors WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); creditors=conn.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    expenses=conn.execute("SELECT * FROM expenses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); losses=conn.execute("SELECT * FROM losses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    requests_list=conn.execute("SELECT * FROM requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); submissions=conn.execute("SELECT * FROM submissions WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); alerts=conn.execute("SELECT * FROM alert_requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    items={}
    for r in purch:
        it=r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":safe(r,'cost_price'),"selling_price":safe(r,'selling_price'),"expiry_date":safe(r,'expiry_date'),"min_stock":safe(r,'min_stock'),"max_stock":safe(r,'max_stock')}); items[it]["purch_qty"]+=float(safe(r,'qty') or 0)
    for r in sales:
        it=r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":0,"selling_price":0,"expiry_date":"","min_stock":0,"max_stock":0}); items[it]["sales_qty"]+=float(safe(r,'qty') or 0)
    combined=[]
    for it,d in items.items():
        d["remaining"]=d["purch_qty"]-d["sales_qty"]; d["profit"]=(float(d["selling_price"] or 0)-float(d["cost_price"] or 0))*d["sales_qty"]
        d["status"]="⛔ Out of Stock" if d["remaining"]<=0 else ("⚠️ Low Stock" if d["min_stock"] and d["remaining"]<=float(d["min_stock"]) else "✅ In Stock"); combined.append(d)
    html=STYLE+top(f"Welcome, {session.get('name')} ({display_role(role)})",f"Shop ID {sid} • Today {today_str()}")
    html+=f"""<div class="card"><b>Totals:</b> Sales {fmt(sales_total)} | Purchases {fmt(purch_total)} | Profit {fmt(profit)}<br><br><div class="grid2"><a href="/subscription"><button class="orange">💳 Subscription - View Plans</button></a><a href="/shop-settings"><button class="blue">⚙️ Settings - WhatsApp & Prices</button></a></div>{'<a href="/print-transactions"><button style="margin-top:10px">🖨️ Print Transactions (MD & Manager)</button></a>' if role in ['owner','manager'] else ''}<a href="/logout"><button style="margin-top:10px;background:#64748b">Logout</button></a></div>"""
    html+="<div class='section'>📦 Stock / Inventory</div><div class='card'><table><tr><th>Item</th><th>Purchased</th><th>Sold</th><th>Remaining</th><th>Cost</th><th>Selling</th><th>Expiry</th><th>Status</th></tr>"
    for r in combined: html+=f"<tr><td><b>{r['item']}</b></td><td>{r['purch_qty']}</td><td>{r['sales_qty']}</td><td><b>{r['remaining']}</b></td><td>{fmt(r['cost_price'])}</td><td>{fmt(r['selling_price'])}</td><td>{r['expiry_date'] or '-'}</td><td>{r['status']}</td></tr>"
    html+="</table></div>"
    if role in ['sales','manager','admin','owner']:
        opts="".join([f"<option value='{r['item']}'>{r['item']} - Available {r['remaining']}</option>" for r in combined if r['remaining']>0])
        html+=f"""<div class="section">🛒 Add Sale</div><div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{opts}</select><div class="grid2"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price (₦) Per One</label><input name="price" type="number" step="any" required></div></div><label>Or new item</label><input name="item_new" placeholder="Leave blank if selected above"><button class="green">ADD SALE</button></form></div>"""
    if role in ['manager','admin','owner']:
        html+="""<div class="section">➕ Add Purchase - Manager/Admin Only</div><div class="card"><form method="post" action="/add_purchase"><label>Item Name</label><input name="item" required><div class="grid3"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Cost Price</label><input name="cost_price" type="number" step="any" required></div><div><label>Selling Price</label><input name="selling_price" type="number" step="any" required></div></div><div class="grid3"><div><label>Expiry Date</label><input name="expiry_date" type="date"></div><div><label>Min Stock</label><input name="min_stock" type="number" step="any" value="0"></div><div><label>Max Stock</label><input name="max_stock" type="number" step="any" value="0"></div></div><button class="orange">ADD PURCHASE</button></form></div>"""
    if role in ['sales','manager','admin','owner']:
        html+="<div class='section'>👥 Debtors - People Owing Shop (Sales Adds)</div><div class='card'>"
        if role=='sales': html+="""<form method="post" action="/add_debtor"><label>Customer Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item / Reason</label><input name="item"><button>Add Debtor (Sales Only)</button></form><hr>"""
        for r in debtors: html+=f"<div class='row-card'><div><b>{r['name']}</b> - {fmt(r['amount'])} - {r['status']} - {r['item']}</div><a href='/settle_debtor/{r['id']}'><button class='small green'>Settle</button></a></div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>🏦 Creditors - Shop Owing People (Manager/Admin Only)</div><div class='card'>"
        if role in ['manager','admin']: html+="""<form method="post" action="/add_creditor"><label>Creditor Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item / Reason</label><input name="item"><button>Add Creditor (Manager/Admin Only)</button></form><hr>"""
        for r in creditors: html+=f"<div class='row-card'><div><b>{r['name']}</b> - {fmt(r['amount'])} - {r['status']} - {r['item']}</div><a href='/settle_creditor/{r['id']}'><button class='small'>Settle</button></a></div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>💸 Expenses & Losses</div><div class='card'><form method='post' action='/add_expense'><label>Expense Item</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Note</label><input name='note'><button>Add Expense</button></form><hr><form method='post' action='/add_loss'><label>Loss Item</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Reason</label><input name='reason'><button style='background:#dc2626'>Add Loss</button></form>"
        for r in expenses: html+=f"<div class='row-card'><div><b>Expense: {r['item']}</b> - {r['note']}</div><b>{fmt(r['amount'])}</b></div>"
        for r in losses: html+=f"<div class='row-card'><div><b>Loss: {r['item']}</b> - {r['reason']}</div><b>{fmt(r['amount'])}</b></div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>📩 Requests To MD/CEO - Expenditure / Budget / Salary</div><div class='card'><form method='post' action='/add_request'><label>Type</label><select name='type'><option>Expenditure</option><option>Budget Request</option><option>Salary Schedule</option></select><label>Title</label><input name='title' required><label>Items / Details</label><textarea name='items' placeholder='e.g. 1. Rice 50kg | Qty 2 | ₦50,000'></textarea><label>Amount (₦)</label><input name='amount' type='number' step='any'><label>Note</label><input name='note'><button>Send Request To MD/CEO</button></form><hr>"
        for r in requests_list: html+=f"<div class='row-card'><div><b>{r['type']}: {r['title']}</b> - {r['status']}<br><span class='muted'>{r['items']} | {fmt(r['amount'])}</span><br>{('<b>MD Feedback:</b> '+r['owner_feedback']) if r['owner_feedback'] else ''}</div>{('<a href=\"/approve_request/'+str(r['id'])+'\"><button class=\"small green\">Approve</button></a>') if role=='owner' else ''}</div>"
        html+="</div>"
        html+="<div class='section'>🚨 Alert Requests - To MD/CEO</div><div class='card'><form method='post' action='/add_alert'><label>Alert Item</label><input name='alert_item' required><label>Alert Type</label><select name='alert_type'><option>Low Stock</option><option>Expiry</option><option>Urgent</option><option>Other</option></select><label>Manager Message</label><textarea name='manager_message' required></textarea><button class='orange'>Send Alert</button></form><hr>"
        for r in alerts: html+=f"<div class='row-card'><div><b>{r['alert_item']} - {r['alert_type']}</b> - {r['status']}<br><span class='muted'>{r['manager_message']}</span><br>{('<b>MD Remark:</b> '+r['owner_remark']) if r['owner_remark'] else ''}</div></div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>📋 Submitted Histories To MD/CEO</div><div class='card'><form method='post' action='/submit_history'><label>Period Label (e.g. Today - 23 Nov 2026)</label><input name='period_label' required><label>Summary</label><textarea name='summary' placeholder='Sales, purchases, profit...'></textarea><label>Manager Remark</label><textarea name='manager_remark' required></textarea><button class='blue'>Submit This History To MD/CEO</button></form><hr>"
        for s in submissions: html+=f"<div class='row-card'><div><b>{s['period_label']} - {s['status']}</b><br><span class='muted'>{s['summary']} • {s['date']}</span><br><b>My Remark:</b> {s['manager_remark']}<br>{('<b>MD Remark:</b> '+s['owner_remark']) if s['owner_remark'] else ''}</div></div>"
        html+="</div>"
    if role in ['owner','manager']:
        html+="""<div class="section">👤 Add User</div><div class="card"><form method="post" action="/add_user"><label>Name</label><input name="name" required><label>Username</label><input name="username" required><label>Password</label><input name="password" required><label>Role</label><select name="role"><option value="sales">Salesperson</option><option value="manager">Manager</option><option value="admin">Admin</option></select><button>Add User</button></form></div>"""
    return html+end()

@app.route("/add_user", methods=["POST"])
def add_user():
    if session.get('role') not in ['owner','manager']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO users (shop_id, username, password, role, name) VALUES (?,?,?,?,?)",(session.get('shop_id'),request.form.get("username"),request.form.get("password"),request.form.get("role"),request.form.get("name"))); conn.commit(); return redirect("/shop")

# ---------- ACTIONS ----------
@app.route("/sell", methods=["POST"])
def sell():
    if session.get('role') not in ['sales','manager','admin','owner']: return blocked_msg()
    item=(request.form.get("item_new") or request.form.get("item") or "").strip()
    try: qty=float(request.form.get("qty") or 0); price=float(request.form.get("price") or 0)
    except: return "Invalid qty/price <a href='/shop'>Go Back</a>"
    if not item or qty<=0: return "Fill item & qty <a href='/shop'>Go Back</a>"
    remain=stock_remaining(session.get('shop_id'), item)
    if remain<=0: return STYLE+top("Out of Stock","")+f"<div class='card'><h3>⛔ OUT OF STOCK</h3><p>{item} don finish (Remaining: 0). Manager must add Purchase first.</p><a href='/shop'>Go Back</a></div>"+end()
    if qty>remain: return STYLE+top("Not Enough Stock","")+f"<div class='card'><h3>⛔ NOT ENOUGH STOCK</h3><p>You try sell {qty} {item} but only {remain} remain.</p><a href='/shop'>Go Back</a></div>"+end()
    conn=get_db(); total=qty*price; conn.execute("INSERT INTO sales (shop_id, item, qty, price, selling_price, total, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),item,qty,price,price,total,session.get('username'),session.get('role'),today_str())); conn.commit()
    last=conn.execute("SELECT id FROM sales WHERE shop_id=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),)).fetchone(); nid=last["id"] if last else 0
    return STYLE+top("Sale Added","")+f"<div class='card'><h3>✅ Sale Added: {item} x{qty} = {fmt(total)}</h3><p>Remaining now: {remain-qty}</p><a href='/sale-whatsapp/{nid}'><button class='green'>📲 Send WhatsApp to MD & Manager</button></a><br><br><a href='/shop'>Go Back to Shop</a></div>"+end()

@app.route("/add_purchase", methods=["POST"])
def add_purchase():
    if session.get('role') not in ['manager','admin','owner']: return blocked_msg("Only Manager/Admin fit add purchase.")
    conn=get_db(); qty=float(request.form.get("qty") or 0); cp=float(request.form.get("cost_price") or 0); sp=float(request.form.get("selling_price") or 0)
    conn.execute("INSERT INTO purchases (shop_id, item, qty, price, cost_price, selling_price, total, expiry_date, min_stock, max_stock, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),qty,cp,cp,sp,qty*cp,request.form.get("expiry_date",""),float(request.form.get("min_stock") or 0),float(request.form.get("max_stock") or 0),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/add_debtor", methods=["POST"])
def add_debtor():
    if session.get('role')!='sales': return blocked_msg("Only Salesperson fit add debtor.")
    conn=get_db(); conn.execute("INSERT INTO debtors (shop_id, name, amount, phone, item, reason, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("item",""),"Owing",session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/settle_debtor/<int:did>")
def settle_debtor(did):
    conn=get_db(); conn.execute("UPDATE debtors SET status='Paid', paid_amount=amount WHERE id=? AND shop_id=?",(did,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/add_creditor", methods=["POST"])
def add_creditor():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit add creditor. Sales cannot add creditor.")
    conn=get_db(); conn.execute("INSERT INTO creditors (shop_id, name, amount, phone, item, reason, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("item",""),"Owing",session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/settle_creditor/<int:cid>")
def settle_creditor(cid):
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit settle creditor.")
    conn=get_db(); conn.execute("UPDATE creditors SET status='Paid', paid_amount=amount WHERE id=? AND shop_id=?",(cid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/add_expense", methods=["POST"])
def add_expense():
    if session.get('role') not in ['manager','admin','owner']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO expenses (shop_id, item, amount, note, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("note",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/add_loss", methods=["POST"])
def add_loss():
    if session.get('role') not in ['manager','admin','owner']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO losses (shop_id, item, amount, note, reason, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("reason",""),request.form.get("reason",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/add_request", methods=["POST"])
def add_request():
    if session.get('role') not in ['manager','admin','owner']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO requests (shop_id, type, title, amount, note, items, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("type"),request.form.get("title"),float(request.form.get("amount") or 0),request.form.get("note",""),request.form.get("items",""),"Pending",session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/approve_request/<int:rid>")
def approve_request(rid):
    if session.get('role')!='owner': return blocked_msg("Only MD/CEO fit approve.")
    conn=get_db(); conn.execute("UPDATE requests SET status='Approved' WHERE id=? AND shop_id=?",(rid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/add_alert", methods=["POST"])
def add_alert():
    if session.get('role') not in ['manager','admin','owner']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO alert_requests (shop_id, alert_item, alert_type, manager_message, status, created_by, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("alert_item"),request.form.get("alert_type"),request.form.get("manager_message"),"Pending",session.get('username'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/submit_history", methods=["POST"])
def submit_history():
    if session.get('role') not in ['manager','admin']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO submissions (shop_id, period, period_label, summary, status, manager_remark, created_by, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("period_label"),request.form.get("period_label"),request.form.get("summary",""),"Submitted",request.form.get("manager_remark",""),session.get('username'),today_str())); conn.commit(); return redirect("/shop")

# ---------- SUBSCRIPTION / SETTINGS / WHATSAPP / PDF ----------
@app.route("/subscription")
def subscription():
    plans=get_plans(); html=STYLE+top("Subscription","Pay to continue using Omeyi")+f"""<div class="card" style="text-align:center"><img src="{QR_IMG}" style="width:160px;border-radius:12px;border:6px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.15)"><p><b>Scan to open Omeyi</b><br><span class="muted">{APP_URL}</span></p></div>"""
    for p in plans: html+=f"""<div class="card"><b>{p['name']} - {fmt(p['amount'])}</b> - {p['days']} days<br><span class="muted">{PRICE_NOTICE}</span><br><br>Pay to: <b>{PAYMENT_BANK} - {PAYMENT_ACCOUNT} - {PAYMENT_NAME}</b><br><a href="/subscription/pay?plan={p['name']}"><button class="green" style="margin-top:10px">I Don Pay For {p['name']}</button></a></div>"""
    html+=f"""<div class="card"><b>How to pay:</b><br>1. Transfer to {PAYMENT_BANK} <b>{PAYMENT_ACCOUNT}</b> ({PAYMENT_NAME})<br>2. Click I Don Pay<br>3. Super Admin go confirm am.<br><span class="muted">{PRICE_NOTICE}</span></div><a href="/shop">Go Back</a>"""+end(); return html
@app.route("/subscription/pay")
def sub_pay(): return STYLE+top("Payment Submitted","")+f"""<div class="card"><h3>Payment Submitted</h3><p>Plan: {request.args.get('plan')}<br>Pay to: {PAYMENT_BANK} - {PAYMENT_ACCOUNT} - {PAYMENT_NAME}<br><span class="muted">{PRICE_NOTICE}</span></p><p>Super Admin go confirm your payment soon. Keep your transfer receipt.</p><a href="/shop">Go Back</a></div>"""+end()
@app.route("/shop-settings", methods=["GET","POST"])
def shop_settings():
    if session.get('role') not in ['owner','manager','admin','superadmin']: return blocked_msg()
    if request.method=="POST":
        upsert_settings(session.get('shop_id'), request.form.get("md_phone",""), request.form.get("manager_phone",""))
        if session.get('role')=='superadmin':
            conn=get_db(); conn.execute("DELETE FROM subscription_plans")
            for n,a,d in [("Monthly",request.form.get("p1"),30),("Quarterly",request.form.get("p2"),90),("Yearly",request.form.get("p3"),365)]:
                if a: conn.execute("INSERT INTO subscription_plans VALUES (?,?,?)",(n,float(a),d))
            conn.commit()
        return redirect("/shop")
    plans=get_plans(); c=shop_contacts(session.get('shop_id'))
    return STYLE+top("Shop Settings","WhatsApp & Prices")+f"""<div class="card"><form method="post"><label>MD/CEO WhatsApp Number</label><input name="md_phone" value="{c.get('md_phone','')}" placeholder="e.g. 08037372296"><label>Manager WhatsApp Number</label><input name="manager_phone" value="{c.get('manager_phone','')}" placeholder="e.g. 080..."><label>Monthly Price (₦) - Adjustable Anytime</label><input name="p1" value="{plans[0]['amount']:.0f}"><label>Quarterly Price (₦) - Adjustable Anytime</label><input name="p2" value="{plans[1]['amount']:.0f}"><label>Yearly Price (₦) - Adjustable Anytime</label><input name="p3" value="{plans[2]['amount']:.0f}"><p class="muted">{PRICE_NOTICE} - Super Admin fit change prices anytime here, no code change needed.</p><button>Save Settings</button></form></div>"""+end()
@app.route("/sale-whatsapp/<int:sale_id>")
def sale_whatsapp(sale_id):
    conn=get_db(); s=conn.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
    if not s: return "Sale not found"
    c=shop_contacts(session.get('shop_id')); msg=f"New Sale on Omeyi: {s['item']} x{s['qty']} = {fmt(safe(s,'total'))} | Shop ID {s['shop_id']} | By {s['created_by']} | {s['date']}"
    links=""
    if c.get('md_phone'): links+=f"<a href='{wa_link(c['md_phone'],msg)}'><button class='green'>Send to MD/CEO on WhatsApp</button></a><br><br>"
    if c.get('manager_phone'): links+=f"<a href='{wa_link(c['manager_phone'],msg)}'><button class='blue'>Send to Manager on WhatsApp</button></a>"
    if not links: links="<p class='muted'>No WhatsApp numbers yet. Go to Shop Settings add MD & Manager numbers.</p><a href='/shop-settings'>Add Numbers</a>"
    return STYLE+top("WhatsApp Notification","")+f"<div class='card'><p>{msg}</p>{links}<br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/print-transactions")
def print_transactions():
    if session.get('role') not in ['owner','manager']: return blocked_msg("Only MD/CEO & Manager fit print transactions.")
    conn=get_db(); sales=conn.execute("SELECT * FROM sales WHERE shop_id=? ORDER BY date DESC LIMIT 200",(session.get('shop_id'),)).fetchall()
    rows="".join([f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td><td>{r['created_by']}</td></tr>" for r in sales])
    return STYLE+top("Transactions - Print / PDF","Only MD/CEO & Manager")+f"""<div class="card"><p class="muted">Press Ctrl+P or Share > Print for phone to save as PDF.</p><button onclick="window.print()">🖨️ Print / Save as PDF</button><br><br><table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th><th>By</th></tr>{rows}</table></div>"""+end()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

from flask import Flask, request, redirect, session
import datetime, os, sqlite3, urllib.parse
try:
    import psycopg2, psycopg2.extras
except: psycopg2 = None
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "omeyi-secret-key")
DATABASE_URL = os.environ.get("DATABASE_URL")
DB = "shop.db"
APP_URL = "https://omeyi.onrender.com"
PAYMENT_BANK = "Opay"; PAYMENT_ACCOUNT = "8037372296"; PAYMENT_NAME = "Joseph George"
PRICE_NOTICE = "(Prices may be reviewed at any time)"
DEFAULT_PLANS = [{"name":"Monthly","amount":5000,"days":30},{"name":"Quarterly","amount":13000,"days":90},{"name":"Yearly","amount":45000,"days":365}]
LOSS_REASONS = ["Expiry","Broken Seal/Others","Broken Bottles","Damaged","Inferior Products"]
DEBTOR_REASONS = ["Regular/Loyal Customers","Failed POS Transactions","Network Problem","Cut Price","Bonanza","Others"]
TIMELINES = ["1-3 days","4-7 days","8-10 days","10-14 days"]
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
def upsert_settings(sid, md, mg):
    conn=get_db()
    try: conn.execute("INSERT INTO shop_settings (shop_id, md_phone, manager_phone) VALUES (?,?,?)",(sid,md,mg))
    except: conn.execute("UPDATE shop_settings SET md_phone=?, manager_phone=? WHERE shop_id=?",(md,mg,sid))
    conn.commit()
def period_start(period):
    t=datetime.date.today()
    if period=='today': return t.isoformat()
    if period=='week': return (t-datetime.timedelta(days=7)).isoformat()
    if period=='month': return (t-datetime.timedelta(days=30)).isoformat()
    if period=='quarter': return (t-datetime.timedelta(days=90)).isoformat()
    if period=='year': return (t-datetime.timedelta(days=365)).isoformat()
    return '0000-01-01'
def period_totals(rows, date_field='date'):
    t=datetime.date.today()
    def s(days): return sum(float(safe(r,'total') or safe(r,'amount') or 0) for r in rows if str(safe(r,date_field) or '') >= (t-datetime.timedelta(days=days)).isoformat())
    return {"today":s(0),"week":s(7),"month":s(30),"quarter":s(90),"year":s(365)}
def init_db():
    conn=get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY, name TEXT, admin_user TEXT, admin_pass TEXT, is_active INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, shop_id INTEGER, username TEXT UNIQUE, password TEXT, role TEXT, name TEXT, must_change INTEGER DEFAULT 1, pwd_changed_at TEXT DEFAULT '')")
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
    for col in ["must_change INTEGER DEFAULT 1","pwd_changed_at TEXT DEFAULT ''"]:
        try: conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except: pass
    conn.commit(); conn.close()
init_db()
def blocked_msg(m="You are not allowed to post this."): return f"{m} <a href='/shop'>Go Back</a>"
STYLE="""<style>*{box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#eaf0f7;color:#1e293b;padding-bottom:40px}.top{background:linear-gradient(135deg,#0b3d91,#0b5ed7 55%,#0ea5e9);color:#fff;padding:18px 16px;border-bottom:4px solid #f59e0b}.top a{color:#fde68a;font-weight:700}.omeyi{font-size:12px;color:#bfdbfe;margin:0;letter-spacing:3px;text-transform:uppercase;font-weight:800}h1{font-size:24px;margin:6px 0 2px}.sub{color:#dbeafe;font-size:13px;margin:0}.wrap{padding:0 12px 30px;max-width:960px;margin:auto}.card{background:#fff;padding:16px;border-radius:16px;margin-bottom:14px;box-shadow:0 4px 14px rgba(11,61,145,.10);border:1px solid #dbeafe}label{font-size:12px;font-weight:800;color:#0b3d91;text-transform:uppercase}input,select,textarea{padding:12px;margin:6px 0 11px;width:100%;border:1.5px solid #cbd5e1;border-radius:10px;font-size:14px;background:#f8fafc}button{padding:13px;background:#0b3d91;color:#fff;border:none;border-radius:11px;cursor:pointer;width:100%;font-weight:800}button.green{background:#16a34a}button.orange{background:#ea580c}button.blue{background:#0b5ed7}button.red{background:#dc2626}button.small{padding:8px 11px;width:auto;font-size:12px}table{width:100%;border-collapse:collapse}th{background:#0b3d91;color:#fff;padding:11px 8px;font-size:11px;text-align:left}td{padding:11px 8px;font-size:13px;border-bottom:1px solid #e2e8f0}.section{font-size:18px;font-weight:900;margin:20px 2px 10px;color:#0b3d91}.muted{font-size:12px;color:#64748b}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.footer{text-align:center;color:#64748b;font-size:12px;padding:18px 0}.row-card{background:#fff;padding:13px;border-radius:12px;margin-bottom:9px;display:flex;justify-content:space-between;border-left:6px solid #0b5ed7}.meter{background:#e2e8f0;height:12px;border-radius:8px;overflow:hidden}.meter>div{background:linear-gradient(90deg,#0b3d91,#0ea5e9);height:12px}.logout{background:#dc2626!important}.pie{width:150px;height:150px;border-radius:50%;margin:auto}</style>"""
FOOTER='<div class="footer">© Omeyi • All Rights Reserved • Powered by Omeyi Blue</div>'
QR_IMG=f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={APP_URL}"
def top(t,s=""): return f'<div class="top"><p class="omeyi">Omeyi</p><h1>{t}</h1><p class="sub">{s}</p></div><div class="wrap" style="margin-top:16px">'
def end(): return "</div>"+FOOTER
def logout_bar(): return """<div class="card" style="display:flex;gap:10px"><a href="/change-password" style="flex:1"><button class="blue">🔑 Change Password</button></a><a href="/logout" style="flex:1"><button class="logout">🚪 LOGOUT — Click Here To Log Out</button></a></div>"""
def needs_pwd_change(r):
    if not r: return False
    if int(safe(r,'must_change') or 0)==1: return True
    try:
        d=safe(r,'pwd_changed_at')
        if not d: return True
        dt=datetime.date.fromisoformat(str(d)[:10])
        return (datetime.date.today()-dt).days>=90
    except: return False
###
@app.route("/", methods=["GET","POST"])
def login():
    # V10 - LOCKED 1,2,3 + 16 ONLY
    conn=get_db()
    try: shops=conn.execute("SELECT * FROM shops ORDER BY name").fetchall()
    except: shops=[]
    shop_opts="".join([f"<option value='{s['id']}'>{s['name']} (ID {s['id']})</option>" for s in shops])
    if request.method=="POST":
        u=request.form.get("username","").strip()
        p=request.form.get("password","").strip()
        selected_shop=request.form.get("shop_id","").strip()

        # 1. Super Admin ONLY fit login without shop
        if u=="superadmin" and p=="omeyi123":
            session.update(role="superadmin",username="superadmin",shop_id=0,name="Super Admin")
            return redirect("/superadmin")

        # 2. V10 FIX 16: Every other person MUST choose shop
        if not selected_shop:
            return STYLE+top("Login","Choose Your Shop / Company")+f"<div class='card'><h3>⛔ Select Your Shop First</h3><p>Please select your Shop / Company before you login.</p><a href='/'>Go Back</a></div>"+end()

        # 3. V10 FIX 16: Staff must belong to THAT shop
        r=conn.execute("SELECT * FROM users WHERE username=? AND password=? AND shop_id=?",(u,p,selected_shop)).fetchone()
        if r:
            sh=conn.execute("SELECT * FROM shops WHERE id=?",(r["shop_id"],)).fetchone()
            if sh and not sh["is_active"]:
                return STYLE+top("Shop OFF","")+f"<div class='card'><h3>⛔ Shop Subscription OFF</h3><p>Super Admin don put this shop OFF.</p><a href='/'>Go Back</a></div>"+end()
            session.update(role=r["role"],username=r["username"],shop_id=r["shop_id"],name=r["name"])
            if needs_pwd_change(r): return redirect("/change-password?first=1")
            return redirect("/shop")

        # 4. V10 FIX 16: MD/CEO must belong to THAT shop too
        s2=conn.execute("SELECT * FROM shops WHERE id=? AND admin_user=? AND admin_pass=?",(selected_shop,u,p)).fetchone()
        if s2:
            if not s2["is_active"]:
                return STYLE+top("Shop OFF","")+f"<div class='card'><h3>⛔ Shop Subscription OFF</h3><p>Super Admin don put this shop OFF.</p><a href='/'>Go Back</a></div>"+end()
            session.update(role="owner",username=u,shop_id=s2["id"],name=s2["name"])
            return redirect("/shop")

        return STYLE+top("Login","Wrong username or password for this shop")+f"<div class='card'><p>That username no belong to the shop you select. Staff of CHRIXMEDIX no fit enter another shop. <a href='/'>Try again</a></div>"+end()

    return STYLE+top("Login","Welcome back")+f"""<div class="card" style="text-align:center"><img src="{QR_IMG}" style="width:150px;border-radius:12px;border:6px solid #fff"><p><b>Scan to open Omeyi</b><br><span class="muted">{APP_URL}</span></p></div><div class="card"><form method="post"><label>Shop / Company — Select Your Shop * Required *</label><select name="shop_id" ><option value="">-- Select Shop / Company --</option>{shop_opts}</select><label>Username</label><input name="username" required><label>Password</label><input name="password" type="password" required><button>LOGIN</button></form><p class='muted'>Super Admin only fit login without selecting shop. All other staff MUST select their shop first.</p></div><div class="card"><b>New Shop?</b> <a href="/subscription">View Subscription Plans</a><br><span class="muted">Pay to {PAYMENT_BANK} {PAYMENT_ACCOUNT} ({PAYMENT_NAME}) - {PRICE_NOTICE}</span></div>"""+end()
#####
@app.route("/logout")
def logout(): session.clear(); return redirect("/")
@app.route("/change-password", methods=["GET","POST"])
def change_password():
    if 'role' not in session: return redirect("/")
    if request.method=="POST":
        old=request.form.get("old_password",""); new=request.form.get("new_password",""); conn=get_db()
        r=conn.execute("SELECT * FROM users WHERE username=? AND password=?",(session.get('username'),old)).fetchone()
        if r:
            conn.execute("UPDATE users SET password=?, must_change=0, pwd_changed_at=? WHERE username=?",(new,today_str(),session.get('username'))); conn.commit(); return redirect("/shop")
        s=conn.execute("SELECT * FROM shops WHERE admin_user=? AND admin_pass=?",(session.get('username'),old)).fetchone()
        if s:
            conn.execute("UPDATE shops SET admin_pass=? WHERE id=?",(new,s["id"])); conn.commit(); return redirect("/shop")
        return STYLE+top("Change Password","Wrong old password")+"<div class='card'><p>Old password no match. <a href='/change-password'>Try again</a></p></div>"+end()
    first=request.args.get("first")
    return STYLE+top("Change Password","All staff fit change password. First login + every 90 days go prompt you.")+f"""<div class="card">{'<p><b>⚠️ Please change your password now — first login / 90 days don reach.</b></p>' if first else ''}<form method="post"><label>Old Password</label><input name="old_password" type="password" required><label>New Password</label><input name="new_password" type="password" required><button class="green">Change Password</button></form></div>"""+logout_bar()+end()
@app.route("/superadmin")
def superadmin():
    if session.get('role')!='superadmin': return blocked_msg("Only Super Admin.")
    conn=get_db(); shops=conn.execute("SELECT * FROM shops ORDER BY id DESC").fetchall()
    traffic=[]
    for s in shops:
        sc=conn.execute("SELECT COUNT(*) as c FROM sales WHERE shop_id=?",(s["id"],)).fetchone()
        pc=conn.execute("SELECT COUNT(*) as c FROM purchases WHERE shop_id=?",(s["id"],)).fetchone()
        rc=conn.execute("SELECT COUNT(*) as c FROM requests WHERE shop_id=?",(s["id"],)).fetchone()
        uc=conn.execute("SELECT COUNT(*) as c FROM users WHERE shop_id=?",(s["id"],)).fetchone()
        total=int(safe(sc,'c'))+int(safe(pc,'c'))+int(safe(rc,'c'))+int(safe(uc,'c'))
        traffic.append({"shop":s,"sales":int(safe(sc,'c')),"purchases":int(safe(pc,'c')),"total":total})
    traffic_sorted=sorted(traffic, key=lambda x: x["total"], reverse=True)
    max_t=max([t["total"] for t in traffic_sorted], default=1) or 1
    rows="".join([f"<tr><td>{t['shop']['name']}</td><td>{t['shop']['admin_user']}</td><td>{'🟢 ON' if t['shop']['is_active'] else '🔴 OFF'}</td><td>{t['sales']} sales / {t['purchases']} purch</td><td><b>{t['total']}</b></td><td>< <a href='/edit-shop/{t['shop']['id']}'>Edit</a> | <a href='/toggle-shop/{t['shop']['id']}'>ON/OFF</a> | <a href='/delete-shop/{t['shop']['id']}' onclick=\"return confirm('Delete this shop?')\" style='color:#dc2626;font-weight:800'>Delete</a></td></tr>" for t in traffic_sorted])
    meter="".join([f"<div class='row-card'><div><b>#{i+1} {t['shop']['name']}</b> — {t['total']} activities<br><div class='meter' style='width:220px;margin-top:6px'><div style='width:{int(t['total']/max_t*100) if max_t else 0}%'></div></div></div><b>{t['total']}</b></div>" for i,t in enumerate(traffic_sorted)])
    shop_opts="".join([f"<option value='{s['id']}'>{s['name']} (ID {s['id']})</option>" for s in shops])
    return STYLE+top("Super Admin","Create MD & Staff, Edit, Delete, ON/OFF, Traffic")+f"""<div class="card"><b>Create Shop + MD/CEO</b><form method="post" action="/create-shop"><label>Shop Name</label><input name="name" required><label>MD/CEO Username</label><input name="admin_user" required><label>MD/CEO Password</label><input name="admin_pass" required><button>Create Shop</button></form></div><div class="card"><b>Create MD / Staff — ONLY Super Admin Creates</b><form method="post" action="/superadmin-create-user"><label>Select Shop</label><select name="shop_id">{shop_opts}</select><label>Full Name</label><input name="name" required><label>Username</label><input name="username" required><label>Password</label><input name="password" required><label>Role</label><select name="role"><option value="owner">MD/CEO</option><option value="manager">Manager</option><option value="sales">Salesperson</option><option value="admin">Admin</option></select><button class="green">Create MD / Staff</button></form></div><div class="card"><b>📊 Traffic Meter — Rank by Highest</b><br>{meter or 'No traffic yet.'}</div><div class="card"><table><tr><th>Shop</th><th>MD User</th><th>Sub</th><th>Traffic</th><th>Total</th><th>Action</th></tr>{rows}</table></div><div class="card"><a href="/shop-settings"><button class="blue">⚙️ Edit Subscription Prices</button></a></div>"""+logout_bar()+end()
@app.route("/create-shop", methods=["POST"])
def create_shop():
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO shops (name, admin_user, admin_pass) VALUES (?,?,?)",(request.form.get("name"),request.form.get("admin_user"),request.form.get("admin_pass"))); conn.commit()
    try:
        sid=conn.execute("SELECT id FROM shops WHERE admin_user=? ORDER BY id DESC LIMIT 1",(request.form.get("admin_user"),)).fetchone()
        conn.execute("INSERT INTO users (shop_id, username, password, role, name, must_change, pwd_changed_at) VALUES (?,?,?,?,?,1,?)",(sid["id"],request.form.get("admin_user"),request.form.get("admin_pass"),"owner",request.form.get("name"),today_str())); conn.commit()
    except: pass
    return redirect("/superadmin")
@app.route("/superadmin-create-user", methods=["POST"])
def superadmin_create_user():
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); sid=int(request.form.get("shop_id") or 0); role=request.form.get("role"); u=request.form.get("username","").strip(); p=request.form.get("password","").strip(); nm=request.form.get("name")
    try:
        conn.execute("INSERT INTO users (shop_id, username, password, role, name, must_change, pwd_changed_at) VALUES (?,?,?,?,?,1,?)",(sid,u,p,role,nm,today_str()))
        if role=='owner': conn.execute("UPDATE shops SET admin_user=?, admin_pass=? WHERE id=?",(u,p,sid))
        conn.commit()
    except: return "Username don exist. <a href='/superadmin'>Go Back</a>"
    return redirect("/superadmin")
@app.route("/edit-shop/<int:sid>", methods=["GET","POST"])
def edit_shop(sid):
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db()
    if request.method=="POST":
        conn.execute("UPDATE shops SET name=?, admin_user=?, admin_pass=? WHERE id=?",(request.form.get("name"),request.form.get("admin_user"),request.form.get("admin_pass"),sid)); conn.commit(); return redirect("/superadmin")
    s=conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone()
    return STYLE+top("Edit Shop","Super Admin")+f"""<div class="card"><form method="post"><label>Shop Name</label><input name="name" value="{s['name']}" required><label>MD Username</label><input name="admin_user" value="{s['admin_user']}" required><label>MD Password</label><input name="admin_pass" value="{s['admin_pass']}" required><button>Save</button></form></div><a href="/superadmin">Back</a>"""+end()
@app.route("/toggle-shop/<int:sid>")
def toggle_shop(sid):
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db(); s=conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone(); conn.execute("UPDATE shops SET is_active=? WHERE id=?",(0 if s["is_active"] else 1,sid)); conn.commit(); return redirect("/superadmin")
@app.route("/delete-shop/<int:sid>")
def delete_shop(sid):
    if session.get('role')!='superadmin': return blocked_msg()
    conn=get_db()
    for tbl in ["sales","purchases","debtors","creditors","losses","expenses","requests","submissions","alert_requests","users"]:
        try: conn.execute(f"DELETE FROM {tbl} WHERE shop_id=?",(sid,))
        except: pass
    try: conn.execute("DELETE FROM shop_settings WHERE shop_id=?",(sid,))
    except: pass
    conn.execute("DELETE FROM shops WHERE id=?",(sid,)); conn.commit(); return redirect("/superadmin")
@app.route("/shop")
def shop():
    if session.get("role") == "superadmin":
        return redirect("/superadmin")
    if 'role' not in session: return redirect("/")
    conn=get_db(); sid=session.get('shop_id'); role=session.get('role'); me=session.get('username')
    period=request.args.get("period","all"); pstart=period_start(period)
    shop_rec=None
    try: shop_rec=conn.execute("SELECT * FROM shops WHERE id=?",(sid,)).fetchone()
    except: pass
    staff_list=conn.execute("SELECT * FROM users WHERE shop_id=? AND role!='owner' ORDER BY id",(sid,)).fetchall() if sid else []
    sales_all=conn.execute("SELECT * FROM sales WHERE shop_id=?",(sid,)).fetchall(); purch=conn.execute("SELECT * FROM purchases WHERE shop_id=?",(sid,)).fetchall()
    sales=[s for s in sales_all if str(safe(s,'date') or '')>=pstart] if period!='all' else sales_all
    sales_total=sum(float(safe(r,'total') or 0) for r in sales_all); purch_total=sum(float(safe(r,'total') or 0) for r in purch)
    gross_profit=sum((float(safe(r,'selling_price') or 0)-float(safe(r,'cost_price') or 0))*float(safe(r,'qty') or 0) for r in sales_all)
    total_losses=sum(float(safe(r,'amount') or 0) for r in conn.execute("SELECT * FROM losses WHERE shop_id=?",(sid,)).fetchall())
    total_exp=sum(float(safe(r,'amount') or 0) for r in conn.execute("SELECT * FROM expenses WHERE shop_id=?",(sid,)).fetchall())
    profit_loss=gross_profit-total_losses-total_exp
    debtors=conn.execute("SELECT * FROM debtors WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall(); creditors=conn.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall()
    expenses=conn.execute("SELECT * FROM expenses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); losses=conn.execute("SELECT * FROM losses WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    requests_list=conn.execute("SELECT * FROM requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall(); submissions=conn.execute("SELECT * FROM submissions WHERE shop_id=? ORDER BY id DESC LIMIT 50",(sid,)).fetchall(); alerts=conn.execute("SELECT * FROM alert_requests WHERE shop_id=? ORDER BY id DESC LIMIT 30",(sid,)).fetchall()
    items={}
    for r in purch:
        it=r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":safe(r,'cost_price'),"selling_price":safe(r,'selling_price'),"expiry_date":safe(r,'expiry_date'),"min_stock":safe(r,'min_stock'),"max_stock":safe(r,'max_stock')}); items[it]["purch_qty"]+=float(safe(r,'qty') or 0)
    for r in sales_all:
        it=r["item"]; items.setdefault(it,{"item":it,"purch_qty":0,"sales_qty":0,"cost_price":0,"selling_price":0,"expiry_date":"","min_stock":0,"max_stock":0}); items[it]["sales_qty"]+=float(safe(r,'qty') or 0)
    combined=[]
    for it,d in items.items():
        d["remaining"]=d["purch_qty"]-d["sales_qty"]; d["profit"]=(float(d["selling_price"] or 0)-float(d["cost_price"] or 0))*d["sales_qty"]
        d["status"]="⛔ Out" if d["remaining"]<=0 else ("⚠️ Low" if d["min_stock"] and d["remaining"]<=float(d["min_stock"]) else "✅ In Stock"); combined.append(d)
    stock_val_cost=sum(float(r["remaining"])*float(r["cost_price"] or 0) for r in combined)
    stock_val_sell=sum(float(r["remaining"])*float(r["selling_price"] or 0) for r in combined)
    opening_cost=purch_total; opening_sell=sum(float(safe(r,'qty') or 0)*float(safe(r,'selling_price') or 0) for r in purch)
    closing_cost=stock_val_cost; closing_sell=stock_val_sell
    perf={}
    for r in sales:
        it=r["item"]; perf.setdefault(it,{"item":it,"qty":0,"profit":0,"total":0})
        perf[it]["qty"]+=float(safe(r,'qty') or 0); perf[it]["profit"]+=(float(safe(r,'selling_price') or 0)-float(safe(r,'cost_price') or 0))*float(safe(r,'qty') or 0); perf[it]["total"]+=float(safe(r,'total') or 0)
    perf_list=list(perf.values()); most_selling=sorted(perf_list, key=lambda x: x["qty"], reverse=True)[:5]; most_profit=sorted(perf_list, key=lambda x: x["profit"], reverse=True)[:5]
    # Auto Alerts V9
    auto_alerts=[]
    for r in combined:
        if r["min_stock"] and r["remaining"]<=float(r["min_stock"]) and r["remaining"]>0: auto_alerts.append(f"⚠️ LOW STOCK: {r['item']} — {r['remaining']} remain (Min {r['min_stock']}) — Expedited Action Needed")
        if r["remaining"]<=0: auto_alerts.append(f"⛔ OUT OF STOCK: {r['item']} — 0 remain")
        if r["expiry_date"]:
            try:
                exp=datetime.date.fromisoformat(str(r["expiry_date"])[:10]); days=(exp-datetime.date.today()).days
                if 0<=days<=30: auto_alerts.append(f"⏰ EXPIRY ALERT: {r['item']} — Expires {r['expiry_date']} ({days} days left) — Expedited Action Needed")
                elif days<0: auto_alerts.append(f"🚨 EXPIRED: {r['item']} — Expired {r['expiry_date']}")
            except: pass
    tl_opts="".join([f"<option>{t}</option>" for t in TIMELINES])
    dr_opts="".join([f"<option>{t}</option>" for t in DEBTOR_REASONS])
    lr_opts="".join([f"<option>{t}</option>" for t in LOSS_REASONS])
    if role=='sales':
        my_sales=[s for s in sales_all if s['created_by']==me]; my_debt=[d for d in debtors if d['created_by']==me]
        st=period_totals(my_sales); dt=period_totals(my_debt,'date')
        html=STYLE+top(f"Welcome, {session.get('name')} (Salesperson)",f"Shop ID {sid} • Today {today_str()}")
        html+=logout_bar()
       # --- STEP 1: Calendar Only Breakdown ---
        bdate = request.args.get("bdate") or today_str()[:10]
        my_sales_day = [s for s in my_sales if str(s.get("date",""))[:10] == bdate]
        my_debt_day = [d for d in my_debt if str(d.get("date",""))[:10] == bdate]
        day_sales_total = sum(float(safe(s,'total') or 0) for s in my_sales_day)
        day_debt_total = sum(float(safe(d,'amount') or 0) for d in my_debt_day)
        html += f"""<div class="section">📊 My Breakdown — Sales & Debtors</div><div class="card"><p>Choose a date to view Sales & Debtors</p><form method="get"><input type="date" name="bdate" value="{bdate}"> <button>View</button></form><p><b>Showing:</b> {bdate} | Total Sales: {fmt(day_sales_total)} | Total Debtors: {fmt(day_debt_total)}</p><table><tr><th>Item</th><th>Qty</th><th>Amount</th><th>Type</th><th>Date</th></tr>"""
        for s in my_sales_day:
            html += f"<tr><td>{s['item']}</td><td>{s['qty']}</td><td>{fmt(safe(s,'total'))}</td><td>Sale</td><td>{s['date']}</td></tr>"
        for d in my_debt_day:
            bal = float(safe(d,'amount') or 0) - float(safe(d,'paid_amount') or 0)
            html += f"<tr><td>{d.get('item','')} - {d['name']}</td><td>-</td><td>{fmt(bal)}</td><td>Debtor</td><td>{d['date']}</td></tr>"
        html += "</table></div>"

        html+="<div class='section'>📦 Inventory / Stock List — With Cost + Selling Price</div><div class='card'><table><tr><th>Item</th><th>Qty In Stock</th><th>Cost Price</th><th>Selling Price</th><th>Status</th></tr>"
        for r in combined: html+=f"<tr><td><b>{r['item']}</b></td><td>{r['remaining']}</td><td>{fmt(r['cost_price'])}</td><td>{fmt(r['selling_price'])}</td><td>{r['status']}</td></tr>"
        html+="</table></div>"
        opts="".join([f"<option value='{r['item']}'>{r['item']} - Available {r['remaining']}</option>" for r in combined if r['remaining']>0])
        html+=f"""<div class="section">🛒 My Sales — Add Sale</div><div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{opts}</select><div class="grid2"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price (₦) Per One</label><input name="price" type="number" step="any" required></div></div><label>Or new item</label><input name="item_new"><button class="green">ADD SALE</button></form></div>"""
        html+=f"<div class='section'>👥 My Debtors — See & Settle Full / Partial + Timeline</div><div class='card'><form method='post' action='/add_debtor'><label>Customer Name</label><input name='name' required><label>Amount (₦)</label><input name='amount' type='number' step='any' required><label>Phone</label><input name='phone'><label>Item</label><input name='item'><label>Reason For Debtor</label><select name='reason'>{dr_opts}</select><label>Settlement Timeline</label><select name='timeframe'>{tl_opts}</select><button>Add Debtor</button></form><hr>"
        for r in my_debt:
            bal=float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            html+=f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)} - {r['status']} - {r['item']} - Reason: {r['reason']} - Timeline: {r['timeframe']}</div><a href='/settle_debtor_form/{r['id']}'><button class='small green'>Settle Full / Partial</button></a></div>"
        html+="</div>"
        html+="<div class='section'>🧾 My Sales Records</div><div class='card'><table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th></tr>"
        for r in my_sales: html+=f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td></tr>"
        html+="</table></div>"
        return html+logout_bar()+end()
    html=STYLE+top(f"Welcome, {session.get('name')} ({display_role(role)})",f"Shop ID {sid} • Today {today_str()}")
    html+=logout_bar()
    if role=='owner' and shop_rec:
        html+=f"""<div class="card" style="border:2px solid #0b3d91"><div class="section" style="margin:0 0 10px">👑 MD/CEO Details — View Only, No Posts, No Settle</div><table><tr><th>Name</th><td><b>{shop_rec['name']}</b></td></tr><tr><th>Designation</th><td><b>MD/CEO</b></td></tr><tr><th>Shop Name</th><td>{shop_rec['name']}</td></tr><tr><th>Shop ID</th><td>{sid}</td></tr></table></div>"""
    if role=='owner':
        html+="<div class='section'>👥 Staff List + Performance — MD ONLY (MD Off The List)</div><div class='card'><table><tr><th>Name</th><th>Designation</th><th>Username</th><th>Performance</th></tr>"
        for u in staff_list:
            sc=sum(1 for s in sales_all if s['created_by']==u['username']); pc=sum(1 for s in purch if s['created_by']==u['username']); rc=sum(1 for s in requests_list if s['created_by']==u['username'])
            html+=f"<tr><td><b>{u['name']}</b></td><td>{display_role(u['role'])}</td><td>{u['username']}</td><td>{sc} sales / {pc} purch / {rc} req</td></tr>"
        html+="</table><p class='muted'>Only Super Admin creates staff. MD only can view this list.</p></div>"
    if role in ['owner','manager']:
        dash_date = request.args.get("dash_date") or today_str()[:10]
        html += f"""<div class="card"><b>📊 Dashboard Totals — MD & Manager</b><p>Choose a date to view Totals & Stock Values</p><form method="get"><input type="date" name="dash_date" value="{dash_date}"> <button>View</button></form><p><b>Showing:</b> {dash_date}</p><table>"""
        if role=='owner':
            html += f"""<tr><th>Opening Stock Value (Cost)</th><td>{fmt(opening_cost)}</td></tr><tr><th>Opening Stock Value (Selling)</th><td>{fmt(opening_sell)}</td></tr><tr><th>Closing Stock Value (Cost)</th><td>{fmt(closing_cost)}</td></tr><tr><th>Closing Stock Value (Selling)</th><td>{fmt(closing_sell)}</td></tr>"""
        html += f"""<tr><th>Total Stock Value (Cost)</th><td>{fmt(stock_val_cost)}</td></tr><tr><th>Total Stock Value (Selling)</th><td>{fmt(stock_val_sell)}</td></tr><tr><th>Total Sales Value</th><td>{fmt(sales_total)}</td></tr><tr><th>Total Purchases Value</th><td>{fmt(purch_total)}</td></tr><tr><th>Gross Profit Value</th><td>{fmt(gross_profit)}</td></tr><tr><th>Total Profit / Loss Value (Gross - Losses - Expenses)</th><td><b>{fmt(profit_loss)}</b></td></tr></table><br><div class="grid2"><a href="/subscription"><button class="orange">💳 Subscription</button></a><a href="/shop-settings"><button class="blue">⚙️ WhatsApp Settings</button></a></div>{'<a href="/print-transactions"><button style="margin-top:10px">🖨️ Print Transactions</button></a>' if role in ['owner','manager'] else ''}</div>"""

    if role=='owner':
        total_perf=sum(x["total"] for x in perf_list) or 1; colors=["#0b3d91","#0ea5e9","#16a34a","#f59e0b","#dc2626"]; segs=[]; start=0
        for i,x in enumerate(most_selling):
            pct=x["total"]/total_perf*100; segs.append(f"{colors[i%len(colors)]} {start:.1f}% {start+pct:.1f}%"); start+=pct
        grad=f"conic-gradient({', '.join(segs)})" if segs else "conic-gradient(#e2e8f0 0% 100%)"
        legend="".join([f"<div><span style='display:inline-block;width:12px;height:12px;background:{colors[i%len(colors)]}'></span> {x['item']} — {fmt(x['total'])} ({x['total']/total_perf*100:.1f}%)</div>" for i,x in enumerate(most_selling)])
        html+=f"""<div class='section'>📊 Pie Chart — Performance — MD ONLY</div><div class='card' style='text-align:center'><div class='pie' style='background:{grad}'></div><br>{legend or 'No sales yet'}<p class='muted'>Pie shows share of sales by product for selected period.</p></div>"""
    if role=='owner':
        total_profit_perf = sum(float(x.get("profit",0) or 0) for x in most_profit) or 1
        colors2 = ["#16a34a","#0b3d91","#f59e0b","#dc2626","#0ea5e9"]
        segs2 = []; start2 = 0
        for i,x in enumerate(most_profit):
            pct = float(x.get("profit",0) or 0)/total_profit_perf*100
            segs2.append(f"{colors2[i%len(colors2)]} {start2:.1f}% {start2+pct:.1f}%"); start2 += pct
        grad2 = f"conic-gradient({', '.join(segs2)})" if segs2 else "conic-gradient(#e2e8f0 0% 100%)"
        legend2 = "".join([f"<div><span style='display:inline-block;width:12px;height:12px;background:{colors2[i%len(colors2)]}'></span> {x['item']} — {fmt(x['profit'])} ({float(x.get('profit',0) or 0)/total_profit_perf*100:.1f}%)</div>" for i,x in enumerate(most_profit)])
        html += f"""<div class='section'>📊 Pie Chart 2 — Most Profitable Product — MD ONLY</div><div class='card' style='text-align:center'><div class='pie' style='background:{grad2}'></div><br>{legend2 or 'No sales yet'}<p class='muted'>Pie 1 = Most Selling (by Total). Pie 2 = Most Profitable (by Profit) for selected period.</p></div>"""

    html+="<div class='section'>📦 Stock / Inventory</div><div class='card'><table><tr><th>Item</th><th>Purchased</th><th>Sold</th><th>Remaining</th><th>Cost</th><th>Selling</th><th>Expiry</th><th>Status</th></tr>"
    for r in combined: html+=f"<tr><td><b>{r['item']}</b></td><td>{r['purch_qty']}</td><td>{r['sales_qty']}</td><td><b>{r['remaining']}</b></td><td>{fmt(r['cost_price'])}</td><td>{fmt(r['selling_price'])}</td><td>{r['expiry_date'] or '-'}</td><td>{r['status']}</td></tr>"
    html+="</table></div>"
    if role=='admin':
        opts="".join([f"<option value='{r['item']}'>{r['item']} - Available {r['remaining']}</option>" for r in combined if r['remaining']>0])
        html+=f"""<div class="section">🛒 Add Sale - Admin Only</div><div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{opts}</select><div class="grid2"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price (₦)</label><input name="price" type="number" step="any" required></div></div><label>Or new item</label><input name="item_new"><button class="green">ADD SALE</button></form></div>"""
    if role in ['manager','admin']:
        html+="""<div class="section">➕ Add Purchase - Manager/Admin Only</div><div class="card"><form method="post" action="/add_purchase"><label>Item Name</label><input name="item" required><div class="grid3"><div><label>Qty</label><input name="qty" type="number" step="any" required></div><div><label>Cost Price</label><input name="cost_price" type="number" step="any" required></div><div><label>Selling Price</label><input name="selling_price" type="number" step="any" required></div></div><div class="grid3"><div><label>Expiry Date</label><input name="expiry_date" type="date"></div><div><label>Min Stock</label><input name="min_stock" type="number" step="any" value="0"></div><div><label>Max Stock</label><input name="max_stock" type="number" step="any" value="0"></div></div><button class="orange">ADD PURCHASE</button></form></div>"""
    if role in ['manager','admin','owner']:
        html+="<div class='section'>👥 Debtors — MD View Only, Manager NO Settle</div><div class='card'>"
        if role=='admin': html+=f"""<form method="post" action="/add_debtor_admin"><label>Customer Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item</label><input name="item"><label>Reason</label><select name="reason">{dr_opts}</select><label>Timeline</label><select name="timeframe">{tl_opts}</select><button>Add Debtor (Admin)</button></form><hr>"""
        for r in debtors:
            bal=float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            btn=f"<a href='/settle_debtor_form/{r['id']}'><button class='small green'>Settle Full / Partial</button></a>" if role=='admin' else "<span class='muted'>View Only</span>"
            html+=f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Bal {fmt(bal)} - {r['status']} - Reason: {r['reason']} - Timeline: {r['timeframe']}</div>{btn}</div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>🏦 Creditors — MD View Only, Manager + Admin Can Settle Full / Partial</div><div class='card'>"
        if role in ['manager','admin']: html+=f"""<form method="post" action="/add_creditor"><label>Creditor Name</label><input name="name" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Phone</label><input name="phone"><label>Item / Reason</label><input name="item"><label>Settlement Timeline</label><select name="timeframe">{tl_opts}</select><button>Add Creditor</button></form><hr>"""
        for r in creditors:
            bal=float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
            btn=f"<a href='/settle_creditor_form/{r['id']}'><button class='small'>Settle Full / Partial</button></a>" if role in ['manager','admin'] else "<span class='muted'>View Only</span>"
            html+=f"<div class='row-card'><div><b>{r['name']}</b> - Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Bal {fmt(bal)} - {r['status']} - Timeline: {r['timeframe']}</div>{btn}</div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>💸 Losses & Expenses</div><div class='card'>"
        if role in ['manager','admin']: html+=f"<form method='post' action='/add_loss'><label>Loss Item</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Reason For Loss</label><select name='reason'>{lr_opts}</select><button style='background:#dc2626'>Add Loss (Manager/Admin)</button></form><hr>"
        if role=='admin': html+="<form method='post' action='/add_expense'><label>Expense Item (Admin Direct)</label><input name='item' required><label>Amount</label><input name='amount' type='number' step='any' required><label>Note</label><input name='note'><button>Add Expense (Admin Only)</button></form><hr>"
        for r in expenses: html+=f"<div class='row-card'><div><b>Expense: {r['item']}</b> - {r['note']}</div><b>{fmt(r['amount'])}</b></div>"
        for r in losses: html+=f"<div class='row-card'><div><b>Loss: {r['item']}</b> - Reason: {r['reason']}</div><b>{fmt(r['amount'])}</b></div>"
        html+="</div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>📩 Requests To MD/CEO</div><div class='card'>"
        if role in ['manager','admin']: html+="<form method='post' action='/add_request'><label>Type</label><select name='type'><option>Expenditure</option><option>Budget Request</option><option>Salary Schedule</option><option>Expense Request</option></select><label>Title</label><input name='title' required><label>Items / Details</label><textarea name='items'></textarea><label>Amount (₦)</label><input name='amount' type='number' step='any'><label>Notes</label><textarea name='note' required></textarea><button>Send Request To MD/CEO</button></form><hr>"
        for r in requests_list:
            md_form=""
            if role=='owner' and r['status']=='Pending': md_form=f"""<form method="post" action="/md_remark/{r['id']}" style="margin-top:8px"><label>MD Remark — Approve</label><textarea name="remark" required></textarea><button class="small green">Save Remark & Approve</button></form><form method="post" action="/md_reject/{r['id']}" style="margin-top:6px"><label>MD Remark — Reject</label><textarea name="remark" required></textarea><button class="small red">Reject With Remark</button></form>"""
            resubmit=""
            if role in ['manager','admin'] and r['status']=='Rejected': resubmit=f"""<form method="post" action="/resubmit_request/{r['id']}" style="margin-top:8px"><label>Act On MD Remark & Resubmit</label><textarea name="note" required></textarea><button class="small orange">🔁 Resubmit</button></form>"""
            html+=f"<div class='row-card'><div><b>{r['type']}: {r['title']}</b> - {r['status']}<br><span class='muted'>{r['items']} | {fmt(r['amount'])}</span><br><b>Note:</b> {r['note']}<br>{('<b>MD Remark:</b> '+r['owner_feedback']) if r['owner_feedback'] else ''}{md_form}{resubmit}</div></div>"
        html+="</div>"
        html+="<div class='section'>🚨 Alerts — Expiry + Stock Levels + Expedited (Fixed)</div><div class='card'>"
        if auto_alerts: html+="<div style='background:#fef3c7;padding:12px;border-radius:10px;margin-bottom:10px'><b>🔔 Auto Alerts:</b><br>"+"<br>".join(auto_alerts)+"</div>"
        if role in ['manager','admin']: html+="<form method='post' action='/add_alert'><label>Alert Item</label><input name='alert_item' required><label>Alert Type</label><select name='alert_type'><option>Low Stock</option><option>Expiry</option><option>Urgent</option><option>Other</option></select><label>Manager Recommendation + Notes</label><textarea name='manager_message' required></textarea><label><input type='checkbox' name='expedited' value='yes' style='width:auto'> ⚡ EXPEDITED / URGENT</label><br><br><button class='orange'>Send Alert To MD/CEO</button></form><hr>"
        html+="<table><tr><th>Item</th><th>Type</th><th>Recommendation</th><th>Status</th><th>MD Remark</th><th>Action</th></tr>"
        for r in alerts:
            act=""
            if role=='owner' and r['status']=='Pending': act=f"""<form method="post" action="/md_alert_remark/{r['id']}"><input name="remark" placeholder="MD Remark" required><button class="small">Save Remark</button></form>"""
            else: act=f"<span class='muted'>{r['status']}</span>"
            html+=f"<tr><td><b>{r['alert_item']}</b></td><td>{r['alert_type']}</td><td>{r['manager_message']}</td><td>{r['status']}</td><td>{r['owner_remark'] or '-'}</td><td>{act}</td></tr>"
        html+="</table></div>"
    if role in ['manager','admin','owner']:
        html+="<div class='section'>📋 Submitted History For Review — Daily / Weekly / Monthly / Quarterly / Yearly — Internal Control</div><div class='card'>"
        if role in ['manager','admin']: html+="<form method='post' action='/submit_history'><label>Period</label><select name='period'><option>Daily</option><option>Weekly</option><option>Monthly</option><option>Quarterly</option><option>Yearly</option></select><label>Period Label (e.g. Week 1 - Nov 2026)</label><input name='period_label' required><label>Summary</label><textarea name='summary'></textarea><label>Manager Remark / Comment</label><textarea name='manager_remark' required></textarea><button class='blue'>Submit To MD/CEO For Review</button></form><hr><p class='muted'>Manager: review period record, add remark, submit. MD go check, review, validate.</p>"
        for s in submissions:
            md_form=""
            if role=='owner' and s['status']=='Submitted': md_form=f"""<form method="post" action="/md_submission_remark/{s['id']}" style="margin-top:8px"><label>MD Remark — Approve / Validate</label><textarea name="remark" required></textarea><button class="small green">Save MD Remark & Approve</button></form>"""
            html+=f"<div class='row-card'><div><b>{s['period']} — {s['period_label']} - {s['status']}</b><br><span class='muted'>{s['summary']} • {s['date']}</span><br><b>Manager Remark:</b> {s['manager_remark']}<br>{('<b>MD Remark:</b> '+s['owner_remark']) if s['owner_remark'] else ''}{md_form}</div></div>"
        html+="</div>"
    return html+logout_bar()+end()
@app.route("/add_user", methods=["POST"])
def add_user(): return blocked_msg("Only Super Admin fit create staff.")
@app.route("/sell", methods=["POST"])
def sell():
    if session.get('role') not in ['sales','admin']: return blocked_msg("MD & Manager cannot add sale.")
    item=(request.form.get("item_new") or request.form.get("item") or "").strip()
    try: qty=float(request.form.get("qty") or 0); price=float(request.form.get("price") or 0)
    except: return "Invalid qty/price <a href='/shop'>Go Back</a>"
    if not item or qty<=0: return "Fill item & qty <a href='/shop'>Go Back</a>"
    remain=stock_remaining(session.get('shop_id'), item)
    if remain<=0: return STYLE+top("Out of Stock","")+f"<div class='card'><h3>⛔ OUT OF STOCK</h3><p>{item} don finish.</p><a href='/shop'>Go Back</a></div>"+end()
    if qty>remain: return STYLE+top("Not Enough Stock","")+f"<div class='card'><h3>⛔ NOT ENOUGH</h3><p>Only {remain} remain.</p><a href='/shop'>Go Back</a></div>"+end()
    conn=get_db(); total=qty*price
    cp=0
    try:
        pr=conn.execute("SELECT cost_price FROM purchases WHERE shop_id=? AND item=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),item)).fetchone()
        if pr: cp=float(safe(pr,'cost_price') or 0)
    except: pass
    conn.execute("INSERT INTO sales (shop_id, item, qty, price, cost_price, selling_price, total, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),item,qty,price,cp,price,total,session.get('username'),session.get('role'),today_str())); conn.commit()
    last=conn.execute("SELECT id FROM sales WHERE shop_id=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),)).fetchone(); nid=last["id"] if last else 0
    return STYLE+top("Sale Added","")+f"<div class='card'><h3>✅ Sale Added: {item} x{qty} = {fmt(total)}</h3><a href='/sale-whatsapp/{nid}'><button class='green'>📲 Notify MD & Manager (Sale)</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/add_purchase", methods=["POST"])
def add_purchase():
    if session.get('role') not in ['manager','admin']: return blocked_msg("MD cannot add purchase.")
    conn=get_db(); qty=float(request.form.get("qty") or 0); cp=float(request.form.get("cost_price") or 0); sp=float(request.form.get("selling_price") or 0)
    conn.execute("INSERT INTO purchases (shop_id, item, qty, price, cost_price, selling_price, total, expiry_date, min_stock, max_stock, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),qty,cp,cp,sp,qty*cp,request.form.get("expiry_date",""),float(request.form.get("min_stock") or 0),float(request.form.get("max_stock") or 0),session.get('username'),session.get('role'),today_str())); conn.commit()
    last=conn.execute("SELECT id FROM purchases WHERE shop_id=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),)).fetchone(); nid=last["id"] if last else 0
    return STYLE+top("Purchase Added","")+f"<div class='card'><h3>✅ Purchase Added</h3><a href='/purchase-whatsapp/{nid}'><button class='green'>📲 Notify MD & Manager (Purchase)</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/add_debtor", methods=["POST"])
def add_debtor():
    if session.get('role')!='sales': return blocked_msg("Only Salesperson fit add debtor.")
    conn=get_db(); conn.execute("INSERT INTO debtors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("reason",""),"Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit()
    last=conn.execute("SELECT id FROM debtors WHERE shop_id=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),)).fetchone(); nid=last["id"] if last else 0
    return STYLE+top("Debtor Added","")+f"<div class='card'><h3>✅ Debtor Added</h3><a href='/debtor-whatsapp/{nid}'><button class='green'>📲 Notify MD & Manager (Debtor)</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/add_debtor_admin", methods=["POST"])
def add_debtor_admin():
    if session.get('role')!='admin': return blocked_msg("Only Admin.")
    conn=get_db(); conn.execute("INSERT INTO debtors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("reason",""),"Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/settle_debtor_form/<int:did>", methods=["GET","POST"])
def settle_debtor_form(did):
    if session.get('role') not in ['sales','admin']: return blocked_msg("MD & Manager cannot settle Debtors. Only Sales & Admin.")
    conn=get_db(); r=conn.execute("SELECT * FROM debtors WHERE id=? AND shop_id=?",(did,session.get('shop_id'))).fetchone()
    if not r: return "Debtor not found"
    bal=float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
    if request.method=="POST":
        amt=float(request.form.get("amount") or 0)
        if amt<=0 or amt>bal: return f"Amount must be 1 to {bal}. <a href='/shop'>Go Back</a>"
        new_paid=float(safe(r,'paid_amount') or 0)+amt; status='Paid' if new_paid>=float(safe(r,'amount') or 0)-0.01 else 'Partially Paid'
        conn.execute("UPDATE debtors SET paid_amount=?, status=? WHERE id=?",(new_paid,status,did)); conn.commit()
        return STYLE+top("Debtor Settled","")+f"<div class='card'><h3>✅ {'Full' if status=='Paid' else 'Partial'} Settlement: {fmt(amt)} | Balance Now {fmt(float(safe(r,'amount') or 0)-new_paid)}</h3><a href='/debtor-whatsapp/{did}'><button class='green'>📲 Notify MD & Manager</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
    return STYLE+top("Settle Debtor — Full / Partial","")+f"""<div class="card"><p><b>{r['name']}</b> — Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)} | Timeline {r['timeframe']}</p><form method="post"><label>Amount To Pay Now (Full or Partial)</label><input name="amount" type="number" step="any" max="{bal}" required><p class="muted">Enter full balance {fmt(bal)} for Full, or less for Partial.</p><button class="green">Settle Now</button></form></div>"""+end()
@app.route("/settle_debtor/<int:did>")
def settle_debtor(did): return redirect(f"/settle_debtor_form/{did}")
@app.route("/add_creditor", methods=["POST"])
def add_creditor():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit add creditor.")
    conn=get_db(); conn.execute("INSERT INTO creditors (shop_id, name, amount, phone, item, reason, status, timeframe, paid_amount, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("phone",""),request.form.get("item",""),request.form.get("item",""),"Owing",request.form.get("timeframe",""),0,session.get('username'),session.get('role'),today_str())); conn.commit()
    last=conn.execute("SELECT id FROM creditors WHERE shop_id=? ORDER BY id DESC LIMIT 1",(session.get('shop_id'),)).fetchone(); nid=last["id"] if last else 0
    return STYLE+top("Creditor Added","")+f"<div class='card'><h3>✅ Creditor Added</h3><a href='/creditor-whatsapp/{nid}'><button class='green'>📲 Notify MD & Manager (Creditor)</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/settle_creditor_form/<int:cid>", methods=["GET","POST"])
def settle_creditor_form(cid):
    if session.get('role') not in ['manager','admin']: return blocked_msg("MD cannot settle Creditors. Only Manager & Admin.")
    conn=get_db(); r=conn.execute("SELECT * FROM creditors WHERE id=? AND shop_id=?",(cid,session.get('shop_id'))).fetchone()
    if not r: return "Creditor not found"
    bal=float(safe(r,'amount') or 0)-float(safe(r,'paid_amount') or 0)
    if request.method=="POST":
        amt=float(request.form.get("amount") or 0)
        if amt<=0 or amt>bal: return f"Amount must be 1 to {bal}. <a href='/shop'>Go Back</a>"
        new_paid=float(safe(r,'paid_amount') or 0)+amt; status='Paid' if new_paid>=float(safe(r,'amount') or 0)-0.01 else 'Partially Paid'
        conn.execute("UPDATE creditors SET paid_amount=?, status=? WHERE id=?",(new_paid,status,cid)); conn.commit()
        return STYLE+top("Creditor Settled","")+f"<div class='card'><h3>✅ {'Full' if status=='Paid' else 'Partial'} Settlement: {fmt(amt)} | Balance Now {fmt(float(safe(r,'amount') or 0)-new_paid)}</h3><a href='/creditor-whatsapp/{cid}'><button class='green'>📲 Notify MD & Manager</button></a><br><br><a href='/shop'>Go Back</a></div>"+end()
    return STYLE+top("Settle Creditor — Full / Partial","")+f"""<div class="card"><p><b>{r['name']}</b> — Total {fmt(r['amount'])} | Paid {fmt(safe(r,'paid_amount'))} | Balance {fmt(bal)} | Timeline {r['timeframe']}</p><form method="post"><label>Amount To Pay Now (Full or Partial)</label><input name="amount" type="number" step="any" max="{bal}" required><p class="muted">Enter full balance {fmt(bal)} for Full, or less for Partial.</p><button class="green">Settle Now</button></form></div>"""+end()
@app.route("/settle_creditor/<int:cid>")
def settle_creditor(cid): return redirect(f"/settle_creditor_form/{cid}")
@app.route("/add_expense", methods=["POST"])
def add_expense():
    if session.get('role')!='admin': return blocked_msg("Manager must send Expense Request to MD. Only Admin direct.")
    conn=get_db(); conn.execute("INSERT INTO expenses (shop_id, item, amount, note, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("note",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/add_loss", methods=["POST"])
def add_loss():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit add loss.")
    conn=get_db(); conn.execute("INSERT INTO losses (shop_id, item, amount, note, reason, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("item"),float(request.form.get("amount") or 0),request.form.get("reason",""),request.form.get("reason",""),session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/add_request", methods=["POST"])
def add_request():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit send request.")
    conn=get_db(); conn.execute("INSERT INTO requests (shop_id, type, title, amount, note, items, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("type"),request.form.get("title"),float(request.form.get("amount") or 0),request.form.get("note",""),request.form.get("items",""),"Pending",session.get('username'),session.get('role'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/md_remark/<int:rid>", methods=["POST"])
def md_remark(rid):
    if session.get('role')!='owner': return blocked_msg("Only MD/CEO fit give remark.")
    conn=get_db(); conn.execute("UPDATE requests SET owner_feedback=?, status='Approved' WHERE id=? AND shop_id=?",(request.form.get("remark",""),rid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/md_reject/<int:rid>", methods=["POST"])
def md_reject(rid):
    if session.get('role')!='owner': return blocked_msg("Only MD/CEO fit reject.")
    conn=get_db(); conn.execute("UPDATE requests SET owner_feedback=?, status='Rejected' WHERE id=? AND shop_id=?",(request.form.get("remark",""),rid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/resubmit_request/<int:rid>", methods=["POST"])
def resubmit_request(rid):
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit resubmit.")
    conn=get_db(); r=conn.execute("SELECT * FROM requests WHERE id=? AND shop_id=?",(rid,session.get('shop_id'))).fetchone()
    if not r or r['status']!='Rejected': return blocked_msg("You can only resubmit after MD rejects.")
    conn.execute("UPDATE requests SET note=?, status='Pending' WHERE id=? AND shop_id=?",(request.form.get("note",""),rid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/add_alert", methods=["POST"])
def add_alert():
    if session.get('role') not in ['manager','admin']: return blocked_msg("Only Manager/Admin fit send alert.")
    exp=" ⚡ EXPEDITED / URGENT ACTION" if request.form.get("expedited") else ""
    msg=request.form.get("manager_message","")+exp
    conn=get_db(); conn.execute("INSERT INTO alert_requests (shop_id, alert_item, alert_type, manager_message, status, created_by, date) VALUES (?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("alert_item"),request.form.get("alert_type"),msg,"Pending",session.get('username'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/md_alert_remark/<int:aid>", methods=["POST"])
def md_alert_remark(aid):
    if session.get('role')!='owner': return blocked_msg("Only MD/CEO fit remark on alert.")
    conn=get_db(); conn.execute("UPDATE alert_requests SET owner_remark=?, status='Reviewed' WHERE id=? AND shop_id=?",(request.form.get("remark",""),aid,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/submit_history", methods=["POST"])
def submit_history():
    if session.get('role') not in ['manager','admin']: return blocked_msg()
    conn=get_db(); conn.execute("INSERT INTO submissions (shop_id, period, period_label, summary, status, manager_remark, created_by, date) VALUES (?,?,?,?,?,?,?,?)",(session.get('shop_id'),request.form.get("period"),request.form.get("period_label"),request.form.get("summary",""),"Submitted",request.form.get("manager_remark",""),session.get('username'),today_str())); conn.commit(); return redirect("/shop")
@app.route("/md_submission_remark/<int:sid2>", methods=["POST"])
def md_submission_remark(sid2):
    if session.get('role')!='owner': return blocked_msg("Only MD fit remark on submission.")
    conn=get_db(); conn.execute("UPDATE submissions SET owner_remark=?, status='Approved' WHERE id=? AND shop_id=?",(request.form.get("remark",""),sid2,session.get('shop_id'))); conn.commit(); return redirect("/shop")
@app.route("/subscription")
def subscription():
    if session.get('role')=='sales': return blocked_msg("Salesperson cannot view subscription.")
    plans=get_plans(); html=STYLE+top("Subscription","Pay to continue using Omeyi")+f"""<div class="card" style="text-align:center"><img src="{QR_IMG}" style="width:160px;border-radius:12px;border:6px solid #fff"><p><b>Scan to open Omeyi</b><br><span class="muted">{APP_URL}</span></p></div>"""
    for p in plans: html+=f"""<div class="card"><b>{p['name']} - {fmt(p['amount'])}</b> - {p['days']} days<br><span class="muted">{PRICE_NOTICE}</span><br><br>Pay to: <b>{PAYMENT_BANK} - {PAYMENT_ACCOUNT} - {PAYMENT_NAME}</b><br><a href="/subscription/pay?plan={p['name']}"><button class="green" style="margin-top:10px">I Don Pay For {p['name']}</button></a></div>"""
    html+=f"""<div class="card"><b>How to pay:</b><br>1. Transfer to {PAYMENT_BANK} <b>{PAYMENT_ACCOUNT}</b> ({PAYMENT_NAME})<br>2. Click I Don Pay<br>3. Super Admin go confirm am.</div><a href="/shop">Go Back</a>"""+end(); return html
@app.route("/subscription/pay")
def sub_pay(): return STYLE+top("Payment Submitted","")+f"""<div class="card"><h3>Payment Submitted</h3><p>Plan: {request.args.get('plan')}<br>Pay to: {PAYMENT_BANK} - {PAYMENT_ACCOUNT} - {PAYMENT_NAME}</p><a href="/shop">Go Back</a></div>"""+end()
@app.route("/shop-settings", methods=["GET","POST"])
def shop_settings():
    if session.get('role')=='sales': return blocked_msg("Salesperson cannot view WhatsApp Settings.")
    if session.get('role') not in ['owner','manager','admin','superadmin']: return blocked_msg()
    if request.method=="POST":
        upsert_settings(session.get('shop_id'), request.form.get("md_phone",""), request.form.get("manager_phone",""))
        if session.get('role')=='superadmin':
            conn=get_db(); conn.execute("DELETE FROM subscription_plans")
            for n,a,d in [("Monthly",request.form.get("p1"),30),("Quarterly",request.form.get("p2"),90),("Yearly",request.form.get("p3"),365)]:
                if a: conn.execute("INSERT INTO subscription_plans VALUES (?,?,?)",(n,float(a),d))
            conn.commit()
            if session.get("role") == "superadmin":
                return redirect("/superadmin")
            return redirect("/shop")
    plans=get_plans(); c=shop_contacts(session.get('shop_id'))
    return STYLE+top("WhatsApp Settings","Notifications ONLY to MD & Manager")+f"""<div class="card"><form method="post"><label>MD/CEO WhatsApp Number</label><input name="md_phone" value="{c.get('md_phone','')}" placeholder="e.g. 08037372296"><label>Manager WhatsApp Number</label><input name="manager_phone" value="{c.get('manager_phone','')}" placeholder="e.g. 080..."><label>Monthly Price (₦)</label><input name="p1" value="{plans[0]['amount']:.0f}"><label>Quarterly Price (₦)</label><input name="p2" value="{plans[1]['amount']:.0f}"><label>Yearly Price (₦)</label><input name="p3" value="{plans[2]['amount']:.0f}"><p class="muted">WhatsApp goes to MD & Manager ONLY for: Sales, Purchases, Debtors, Creditors, Settling, Expiry, Stock Levels.</p><button>Save Settings</button></form></div>"""+end()
def notify_page(title,msg):
    c=shop_contacts(session.get('shop_id')); links=""
    if c.get('md_phone'): links+=f"<a href='{wa_link(c['md_phone'],msg)}'><button class='green'>Send to MD/CEO on WhatsApp</button></a><br><br>"
    if c.get('manager_phone'): links+=f"<a href='{wa_link(c['manager_phone'],msg)}'><button class='blue'>Send to Manager on WhatsApp</button></a>"
    if not links: links="<p class='muted'>No WhatsApp numbers yet.</p>"
    return STYLE+top(title,"Notifications to MD & Manager ONLY")+f"<div class='card'><p>{msg}</p>{links}<br><a href='/shop'>Go Back</a></div>"+end()
@app.route("/sale-whatsapp/<int:sale_id>")
def sale_whatsapp(sale_id):
    conn=get_db(); s=conn.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
    if not s: return "Sale not found"
    return notify_page("WhatsApp - Sale",f"🔔 New Sale: {s['item']} x{s['qty']} = {fmt(safe(s,'total'))} | Shop {s['shop_id']} | By {s['created_by']} | {s['date']}")
@app.route("/purchase-whatsapp/<int:pid>")
def purchase_whatsapp(pid):
    conn=get_db(); s=conn.execute("SELECT * FROM purchases WHERE id=?",(pid,)).fetchone()
    if not s: return "Purchase not found"
    return notify_page("WhatsApp - Purchase",f"🔔 New Purchase: {s['item']} x{s['qty']} = {fmt(safe(s,'total'))} | Shop {s['shop_id']} | By {s['created_by']} | {s['date']}")
@app.route("/debtor-whatsapp/<int:did>")
def debtor_whatsapp(did):
    conn=get_db(); s=conn.execute("SELECT * FROM debtors WHERE id=?",(did,)).fetchone()
    if not s: return "Debtor not found"
    return notify_page("WhatsApp - Debtor",f"🔔 Debtor Update: {s['name']} - {fmt(safe(s,'amount'))} - {s['status']} | Shop {s['shop_id']} | {s['date']}")
@app.route("/creditor-whatsapp/<int:cid>")
def creditor_whatsapp(cid):
    conn=get_db(); s=conn.execute("SELECT * FROM creditors WHERE id=?",(cid,)).fetchone()
    if not s: return "Creditor not found"
    return notify_page("WhatsApp - Creditor",f"🔔 Creditor Update: {s['name']} - {fmt(safe(s,'amount'))} - {s['status']} | Shop {s['shop_id']} | {s['date']}")
@app.route("/print-transactions")
def print_transactions():
    if session.get('role') not in ['owner','manager']: return blocked_msg("Only MD/CEO & Manager fit print.")
    conn=get_db(); sales=conn.execute("SELECT * FROM sales WHERE shop_id=? ORDER BY date DESC LIMIT 200",(session.get('shop_id'),)).fetchall()
    rows="".join([f"<tr><td>{r['item']}</td><td>{r['qty']}</td><td>{fmt(safe(r,'total'))}</td><td>{r['date']}</td><td>{r['created_by']}</td></tr>" for r in sales])
    return STYLE+top("Transactions - Print / PDF","Only MD/CEO & Manager")+f"""<div class="card"><button onclick="window.print()">🖨️ Print / Save as PDF</button><br><br><table><tr><th>Item</th><th>Qty</th><th>Total</th><th>Date</th><th>By</th></tr>{rows}</table></div>"""+logout_bar()+end()
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))


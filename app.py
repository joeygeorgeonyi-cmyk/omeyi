from flask import Flask, request, redirect, session, render_template_string
import sqlite3, datetime

app = Flask(__name__)
app.secret_key = "omeyi-secret-key"
DB = "shop.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def safe(row, *names):
    d = dict(row) if row is not None else {}
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return 0

def num_to_words(n):
    try:
        n = int(float(n or 0))
    except:
        return "Zero"
    if n == 0:
        return "Zero"
    ones = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"]
    tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]
    def two(x):
        if x < 20:
            return ones[x]
        return tens[x//10] + (" " + ones[x%10] if x%10 else "")
    def three(x):
        s = ""
        if x >= 100:
            s += ones[x//100] + " Hundred"
            x %= 100
            if x:
                s += " "
        if x:
            s += two(x)
        return s
    parts = []
    for unit, div in [("Billion",1000000000),("Million",1000000),("Thousand",1000)]:
        if n >= div:
            parts.append(three(n//div) + " " + unit)
            n %= div
    if n:
        parts.append(three(n))
    return " ".join(parts)

def today_str():
    return datetime.date.today().isoformat()

def display_role(role):
    if role == 'owner':
        return 'MD/CEO'
    if role == 'manager':
        return 'Manager'
    if role == 'sales':
        return 'Salesperson'
    if role == 'admin':
        return 'Admin'
    if role == 'superadmin':
        return 'Super Admin'
    return role or ''

def init_db():
    conn = get_db()
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
    for tbl in ["sales","purchases","debtors","creditors","losses","expenses","requests","submissions","alert_requests"]:
        for col in ["created_by TEXT DEFAULT ''","created_by_role TEXT DEFAULT ''","date TEXT DEFAULT ''","cost_price REAL DEFAULT 0","selling_price REAL DEFAULT 0","total REAL DEFAULT 0","phone TEXT DEFAULT ''","item TEXT DEFAULT ''","note TEXT DEFAULT ''","name TEXT DEFAULT ''","amount REAL DEFAULT 0","reason TEXT DEFAULT ''","status TEXT DEFAULT 'Owing'","title TEXT DEFAULT ''","type TEXT DEFAULT ''","timeframe TEXT DEFAULT ''","paid_amount REAL DEFAULT 0","items TEXT DEFAULT ''","owner_feedback TEXT DEFAULT ''","expiry_date TEXT DEFAULT ''","min_stock REAL DEFAULT 0","max_stock REAL DEFAULT 0","period TEXT DEFAULT ''","period_label TEXT DEFAULT ''","summary TEXT DEFAULT ''","manager_remark TEXT DEFAULT ''","owner_remark TEXT DEFAULT ''","alert_item TEXT DEFAULT ''","alert_type TEXT DEFAULT ''","manager_message TEXT DEFAULT ''"]:
            try:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
            except:
                pass
    conn.commit()
    conn.close()
init_db()

def is_owner():
    return session.get('role') == 'owner'
def blocked_msg(m="You are not allowed to post this."):
    return f"{m} <a href='/shop'>Go Back</a>"

STYLE = """
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#eaf0f7;color:#1e293b;padding-bottom:40px}
.top{background:linear-gradient(135deg,#0b3d91 0%,#0b5ed7 55%,#0ea5e9 100%);color:#fff;padding:18px 16px 14px;border-bottom:4px solid #f59e0b}
.top a{color:#fde68a;font-weight:700}
.omeyi{font-size:12px;color:#bfdbfe;margin:0;letter-spacing:3px;text-transform:uppercase;font-weight:800}
h1{font-size:24px;margin:6px 0 2px;color:#fff}.sub{color:#dbeafe;font-size:13px;margin:0 0 2px}
.wrap{padding:0 12px 30px;max-width:960px;margin:auto}
.card{background:#ffffff;padding:16px;border-radius:16px;margin-bottom:14px;box-shadow:0 4px 14px rgba(11,61,145,.10);border:1px solid #dbeafe}
label{font-size:12px;font-weight:800;color:#0b3d91;text-transform:uppercase;letter-spacing:.3px}
input,select,textarea{padding:12px;margin:6px 0 11px;width:100%;border:1.5px solid #cbd5e1;border-radius:10px;font-size:14px;background:#f8fafc;color:#1e293b}
input:focus,select:focus,textarea:focus{outline:none;border-color:#0b5ed7;background:#fff;box-shadow:0 0 0 3px rgba(11,94,215,.15)}
button{padding:13px 14px;background:#0b3d91;color:#fff;border:none;border-radius:11px;cursor:pointer;width:100%;font-weight:800;font-size:14px;letter-spacing:.2px}
button:hover{filter:brightness(1.08)}button.blue{background:#0b5ed7}button.green{background:#16a34a}button.orange{background:#ea580c}button.small{padding:8px 11px;width:auto;font-size:12px;border-radius:8px}
.badge{font-size:11px;background:#fef3c7;color:#92400e;padding:5px 10px;border-radius:20px;font-weight:800;border:1px solid #fde68a}
.active{color:#16a34a;font-weight:800}.suspended{color:#dc2626;font-weight:800}
.totals{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.t-box{padding:16px 10px;border-radius:16px;text-align:center;border:1.5px solid;box-shadow:0 3px 10px rgba(0,0,0,.05);background:#fff}
.t-box b{font-size:12px;text-transform:uppercase;letter-spacing:.6px}.t-box .amt{font-size:21px;font-weight:900;margin:7px 0 3px;color:#0b3d91}.t-box .words{font-size:11.5px;line-height:1.35;color:#334155}.t-box small{font-size:11px;color:#64748b}
.b-stock{background:#fffbeb;border-color:#f59e0b}.b-sales{background:#ecfdf5;border-color:#10b981}.b-profit{background:#fff7ed;border-color:#f97316}.b-purch{background:#fef2f2;border-color:#ef4444}.b-debt{background:#eff6ff;border-color:#3b82f6}.b-owe{background:#faf5ff;border-color:#a855f7}.b-bad{background:#fef2f2;border-color:#dc2626}.b-loss{background:#f8fafc;border-color:#64748b}
.section{font-size:18px;font-weight:900;margin:20px 2px 10px;color:#0b3d91}
table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:12px;border:1px solid #dbeafe}
th{background:#0b3d91;color:#fff;padding:11px 8px;font-size:11px;text-align:left;text-transform:uppercase;letter-spacing:.4px}
td{padding:11px 8px;font-size:13px;border-bottom:1px solid #e2e8f0;background:#fff;color:#1e293b}
tr:nth-child(even) td{background:#f8fafc}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.row-card{background:#fff;padding:13px 14px;border-radius:12px;margin-bottom:9px;display:flex;justify-content:space-between;align-items:center;border-left:6px solid #0b5ed7;box-shadow:0 2px 8px rgba(11,61,145,.08)}
.footer{text-align:center;color:#64748b;font-size:12px;padding:18px 0 8px;border-top:1px solid #cbd5e1;margin-top:20px}
.muted{font-size:12px;color:#64748b}
.alert-red{background:#fef2f2;border-left:6px solid #dc2626}.alert-orange{background:#fff7ed;border-left:6px solid #f97316}.alert-yellow{background:#fffbeb;border-left:6px solid #eab308}.alert-purple{background:#faf5ff;border-left:6px solid #a855f7}
.meter{height:14px;background:#e2e8f0;border-radius:20px;overflow:hidden;margin:6px 0}.meter-fill{height:100%;background:linear-gradient(90deg,#0b3d91,#0b5ed7,#0ea5e9);border-radius:20px}
a{color:#0b5ed7}
.success-banner{background:#ecfdf5;border:2px solid #16a34a;color:#065f46;padding:14px;border-radius:12px;font-weight:800;margin-bottom:14px}
.submitted-badge{background:#0b5ed7;color:#fff;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800}
</style>
"""
FOOTER = '<div class="footer">© Omeyi • All Rights Reserved • Powered by Omeyi Blue</div>'

LOGIN_HTML = STYLE + """
<div class="top"><p class="omeyi">Omeyi</p><h1>Login</h1><p class="sub">Welcome back - Manage your shop with confidence</p></div>
<div class="wrap" style="margin-top:16px"><div class="card"><form method="post">
<label>Shop</label><select name="shop_id">{% for s in shops %}<option value="{{s['id']}}">{{s['name']}}</option>{% endfor %}</select>
<label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required>
<button class="blue">LOGIN</button></form><p style="text-align:center"><a href="/super_login">Super Admin Login</a></p></div></div>
""" + FOOTER

SUPER_LOGIN_HTML = STYLE + """
<div class="top"><p class="omeyi">Omeyi</p><h1>Super Admin Login</h1></div>
<div class="wrap" style="margin-top:16px"><div class="card"><form method="post"><label>Username</label><input name="username" required><label>Password</label><input type="password" name="password" required><button class="blue">LOGIN</button></form></div></div>
""" + FOOTER

SUPER_HTML = STYLE + """
<div class="top"><p class="omeyi">Omeyi</p><h1>Super Admin</h1><p class="sub">Traffic / Usage Meter - Who uses Omeyi most?</p></div>
<div class="wrap" style="margin-top:16px">
<div class="card"><h3 style="margin:0 0 6px;color:#0b3d91">📊 Overall Traffic</h3><p style="margin:0">Total Shops: <b>{{total_shops}}</b> • Total Activity (all shops): <b>{{total_activity}}</b> records • Total Staff Accounts: <b>{{total_staff}}</b></p></div>
<div class="card"><h3 style="margin:0 0 10px;color:#0b3d91">🏆 Shops Ranked By Usage - Heaviest First</h3>
{% for s in shops_sorted %}
<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px;background:#f8fafc">
<div style="display:flex;justify-content:space-between"><b>{{loop.index}}. {{s['name']}} {% if loop.index==1 %}🔥 HEAVIEST USE{% endif %}</b><b style="color:#0b5ed7">{{s['traffic_pct']}}%</b></div>
<div class="meter"><div class="meter-fill" style="width:{{s['traffic_pct']}}%"></div></div>
<p style="margin:4px 0;font-size:13px">Activity: <b>{{s['activity']}}</b> records • Staff Accounts: <b>{{s['staff_count']}}</b> • Sales: {{s['sales_count']}} • Purchases: {{s['purch_count']}} • Debtors: {{s['debtors_count']}} • Requests: {{s['requests_count']}}</p>
<p style="margin:0;font-size:12px;color:#64748b">Staff: {{s['users']}} • Status: {% if s['is_active'] %}<span class="active">✅ ACTIVE</span>{% else %}<span class="suspended">❌ OFF</span>{% endif %}</p>
</div>
{% endfor %}
{% if not shops_sorted %}<p class="muted">No shops yet.</p>{% endif %}
</div>
<div class="card"><h3 style="margin:0 0 10px;color:#0b3d91">Create Shop</h3><form method="post" action="/create_shop"><label>Shop Name</label><input name="name" required><button class="blue">Create Shop</button></form></div>
{% for s in shops %}
<div class="card"><h3 style="margin:0;color:#0b3d91">{{s['name']}} <span style="font-size:13px;color:#64748b">(ID: {{s['id']}})</span></h3>
<p>Traffic: <b>{{s['traffic_pct']}}%</b> • Activity: {{s['activity']}} • Staff: {{s['staff_count']}}</p>
<p style="font-size:13px">Staff List: {{ s['users'] }}</p>
<form method="post" action="/add_staff/{{s['id']}}"><b>Add Staff</b><br><br><label>Username</label><input name="username" required><label>Password</label><input name="password" required><label>Name</label><input name="name" placeholder="Full Name"><label>Role</label><select name="role"><option value="owner">MD/CEO</option><option value="manager">Manager</option><option value="admin">Admin</option><option value="sales">Salesperson</option></select><button>ADD STAFF</button></form><br>
<form method="post" action="/toggle_shop/{{s['id']}}"><button>{% if s['is_active'] %}TURN OFF SHOP - Subscription Expired{% else %}TURN ON SHOP - Subscription Active{% endif %}</button></form><br>
<form method="post" action="/delete_shop/{{s['id']}}" onsubmit="return confirm('Delete this shop?')"><button>DELETE SHOP</button></form></div>
{% endfor %}<p><a href="/logout">Logout</a></p></div>
""" + FOOTER

SHOP_HTML = STYLE + """
<div class="top"><p class="omeyi">Omeyi</p><h1>{{shop['name']}} - Dashboard</h1><p class="sub">Logged in as <b>{{session['username']}}</b> <span class="badge">{{display_role}}</span> • <a href="/logout">Logout</a></p>
{% if session['role']=='sales' %}<p style="color:#e0e7ff;font-size:12px;margin:6px 0 0">Salesperson: You see ONLY your own Sales, Debtors, Losses & Profit. No Purchases, No Stock Totals, No other salesperson record.</p>{% endif %}
{% if session['role']=='owner' %}<p style="color:#e0e7ff;font-size:12px;margin:6px 0 0">MD/CEO: View only - you cannot post to records. Approve Manager requests below.</p>{% endif %}
{% if session['role'] in ['manager','admin'] %}<p style="color:#e0e7ff;font-size:12px;margin:6px 0 0">Manager / Admin: You see all Salespersons, Stock Value & Inventory for this period.</p>{% endif %}
</div>
<div class="wrap" style="margin-top:14px">
{% if just_submitted %}
<div class="success-banner">✅ History Submitted To MD/CEO Successfully! MD/CEO will see it now. Status: Submitted - Waiting For MD/CEO Review.</div>
{% endif %}
{% if alert_submitted %}
<div class="success-banner">⚡ Expedited Alert Request Submitted To MD/CEO Successfully! Waiting for MD/CEO instruction.</div>
{% endif %}
{% if session['role'] in ['manager','admin'] and submissions %}
<div class="card" style="border:2px solid #0b5ed7;background:#eff6ff"><b style="color:#0b3d91">📋 YOUR SUBMISSION STATUS - Latest:</b><br>
{% for s in submissions[:1] %}
<div style="margin-top:8px"><b>{{s['period_label']}}</b> - <span class="submitted-badge">{{s['status']}}</span><br><span>{{s['summary']}}</span><br><span><b>Your Remark:</b> {{s['manager_remark']}}</span><br>{% if s['owner_remark'] %}<span><b>MD/CEO Remark:</b> {{s['owner_remark']}}</span><br>{% else %}<span style="color:#0b5ed7">⏳ Waiting for MD/CEO to Approve / Reject...</span>{% endif %}<br><small>Submitted on {{s['date']}} by {{s['created_by']}}</small></div>
{% endfor %}
</div>
{% endif %}
<div class="card"><form method="get" action="/shop"><label>Period:</label><select name="period"><option value="today" {% if period=='today' %}selected{% endif %}>Today</option><option value="week" {% if period=='week' %}selected{% endif %}>This Week</option><option value="month" {% if period=='month' %}selected{% endif %}>This Month</option><option value="quarter" {% if period=='quarter' %}selected{% endif %}>This Quarter</option><option value="year" {% if period=='year' %}selected{% endif %}>This Year</option><option value="all" {% if period=='all' %}selected{% endif %}>All Time</option></select><button class="blue">SHOW TOTALS</button></form><p style="margin:10px 0 0;font-size:13px"><b>Showing: {{period_label}} ({{today}})</b></p></div>

<div class="section">⚠️ Alerts - Expiry / Min / Max / Slow-Moving</div>
<div class="card">
{% if not alerts_expired and not alerts_expiring and not alerts_low and not alerts_over and not alerts_slow %}<p class="muted">✅ No alerts - All stock is healthy.</p>{% endif %}
{% for a in alerts_expired %}<div class="row-card alert-red"><div><b>⛔ EXPIRED - DO NOT SELL: {{a['item']}}</b><br><span>Expired on {{a['expiry_date']}} • Remaining: {{a['remaining']}}</span></div><b>EXPIRED</b></div>{% endfor %}
{% for a in alerts_expiring %}<div class="row-card alert-orange"><div><b>⏰ EXPIRING SOON (30 days): {{a['item']}}</b><br><span>Expiry: {{a['expiry_date']}} • Remaining: {{a['remaining']}}</span></div><b>EXPIRING</b></div>{% endfor %}
{% for a in alerts_low %}<div class="row-card alert-yellow"><div><b>📉 REORDER NOW - Low Stock: {{a['item']}}</b><br><span>Remaining: {{a['remaining']}} • Minimum: {{a['min_stock']}} • Maximum: {{a['max_stock']}} • Last Sold: {{a['last_sold']}}</span></div><b>LOW</b></div>{% endfor %}
{% for a in alerts_over %}<div class="row-card alert-purple"><div><b>📦 OVERSTOCK - Too Much Stock: {{a['item']}}</b><br><span>Remaining: {{a['remaining']}} • Maximum: {{a['max_stock']}} • Minimum: {{a['min_stock']}} • Stop buying this for now</span></div><b>OVERSTOCK</b></div>{% endfor %}
{% for a in alerts_slow %}<div class="row-card alert-yellow"><div><b>🐢 SLOW-MOVING - Sitting Too Long: {{a['item']}}</b><br><span>Last Sold: {{a['last_sold'] or 'Never sold'}} • Remaining: {{a['remaining']}} • Consider promo / price cut</span></div><b>SLOW</b></div>{% endfor %}

{% if session['role'] in ['manager','admin'] %}
<div style="border-top:2px solid #0b3d91;margin-top:14px;padding-top:14px">
<h3 style="margin:0 0 8px;color:#0b3d91">⚡ Expedite Action Request To MD/CEO - For This Alert</h3>
<p class="muted">Manager can suggest action, request permission to carry on an action, or ask MD/CEO for solution.</p>
<form method="post" action="/submit_alert_request">
<label>Which Alert / Item?</label><select name="alert_item">{% for a in combined %}<option value="{{a['item']}} - {{a['status']}}">{{a['item']}} - {{a['status']}} (Remaining: {{a['remaining']}})</option>{% endfor %}{% if not combined %}<option value="General">General - No alert item</option>{% endif %}</select>
<label>Alert Type</label><select name="alert_type"><option>Expiring Soon</option><option>Expired</option><option>Low Stock - Reorder</option><option>Overstock</option><option>Slow-Moving</option><option>Other - Need Advice</option></select>
<label>Your Suggested Action / Request Permission / Ask For Solution</label><textarea name="manager_message" placeholder="e.g. I suggest we sell Paracetamol at discount before expiry. Request permission to do promo. / Request permission to dispose expired drugs. / Please advise - what should we do with overstock of Star Beer?" required></textarea>
<label><input type="checkbox" id="alertCheck" style="width:auto;margin-right:8px" onchange="document.getElementById('alertSubmitBtn').disabled=!this.checked"> ✅ I confirm this expedited request - Send to MD/CEO now</label>
<button id="alertSubmitBtn" class="blue" disabled style="margin-top:8px">⚡ Submit Expedited Request To MD/CEO</button>
</form>
</div>
{% if alert_requests %}
<div style="margin-top:14px"><b>Your Expedited Requests:</b>
{% for ar in alert_requests %}<div style="border:1px solid #dbeafe;border-radius:10px;padding:10px;margin-top:8px;background:#f8fafc"><b>{{ar['alert_item']}} - {{ar['alert_type']}} - {{ar['status']}}</b><br><span><b>You asked:</b> {{ar['manager_message']}}</span><br>{% if ar['owner_remark'] %}<span><b>MD/CEO Instruction:</b> {{ar['owner_remark']}}</span><br>{% else %}<span style="color:#0b5ed7">⏳ Waiting for MD/CEO instruction...</span>{% endif %}<br><small>{{ar['date']}}</small></div>{% endfor %}
</div>
{% endif %}
{% endif %}
</div>

{% if session['role'] in ['owner','manager','admin'] %}
<div class="section">📊 TOTALS - {{period_label}} - Manager / MD/CEO Only</div>
<div class="totals">
<div class="t-box b-stock"><b>Stock / Inventory Value</b><div class="amt">₦{{ "{:,.0f}".format(stock) }}</div><div class="words">{{stock_words}} Naira Only</div><small>For {{period_label}}</small></div>
<div class="t-box b-sales"><b>Sales</b><div class="amt">₦{{ "{:,.0f}".format(sales_total) }}</div><div class="words">{{sales_words}} Naira Only</div><small>{{sales_qty}} sold</small></div>
<div class="t-box b-profit"><b>Gross Profit</b><div class="amt">₦{{ "{:,.0f}".format(profit) }}</div><div class="words">{{profit_words}} Naira Only</div></div>
<div class="t-box b-purch"><b>Purchases</b><div class="amt">₦{{ "{:,.0f}".format(purch_total) }}</div><div class="words">{{purch_words}} Naira Only</div></div>
<div class="t-box b-debt"><b>Debtors Owe You</b><div class="amt">₦{{ "{:,.0f}".format(debtors_total) }}</div><div class="words">{{debtors_words}} Naira Only</div></div>
<div class="t-box b-owe"><b>You Owe (Creditors)</b><div class="amt">₦{{ "{:,.0f}".format(creditors_total) }}</div><div class="words">{{creditors_words}} Naira Only</div></div>
<div class="t-box b-bad"><b>Bad Debt</b><div class="amt">₦0</div><div class="words">Zero Naira Only</div></div>
<div class="t-box b-loss"><b>Losses</b><div class="amt">₦{{ "{:,.0f}".format(losses_total) }}</div><div class="words">{{losses_words}} Naira Only</div></div>
</div>
<div class="section">💰 PROFIT AT A GLANCE - Manager / MD/CEO Only</div>
<div class="card" style="border-left:6px solid #f59e0b"><b style="font-size:16px;color:#0b3d91">Net Profit: ₦{{ "{:,.0f}".format(profit - losses_total - expenses_total) }}</b><div style="font-size:12px;color:#64748b;margin-top:4px">{{net_words}} Naira Only • Gross Profit - Losses - Expenses</div><div style="font-size:12px;margin-top:6px">Expenses: ₦{{ "{:,.0f}".format(expenses_total) }} | Losses: ₦{{ "{:,.0f}".format(losses_total) }}</div></div>
<div class="section">🏆 Most Selling & Most Profitable Products ({{period_label}})</div>
<div class="card">{% for r in top_products %}<div class="row-card"><div><b>{{r['item']}}</b><br><span>Sold: {{r['sales_qty']}} • Profit: ₦{{ "{:,.0f}".format(r['profit']) }}</span></div><b>₦{{ "{:,.0f}".format(r['sales_total']) }}</b></div>{% endfor %}{% if not top_products %}<p class="muted">No sales yet for this period.</p>{% endif %}</div>
<div class="section">👥 Profit Per Salesperson ({{period_label}})</div>
<div class="card">{% for u,amt in profit_by_user.items() %}<div class="row-card"><div><b>{{u}}</b></div><b>₦{{ "{:,.0f}".format(amt) }}</b></div>{% endfor %}{% if not profit_by_user %}<p class="muted">No salesperson profit yet.</p>{% endif %}</div>
{% endif %}

{% if session['role']=='sales' %}
<div class="section">📊 MY TOTALS - {{period_label}} - My Own Only</div>
<div class="totals">
<div class="t-box b-sales"><b>My Sales</b><div class="amt">₦{{ "{:,.0f}".format(sales_total) }}</div><div class="words">{{sales_words}} Naira Only</div><small>{{sales_qty}} sold by me</small></div>
<div class="t-box b-profit"><b>My Profit</b><div class="amt">₦{{ "{:,.0f}".format(profit) }}</div><div class="words">{{profit_words}} Naira Only</div></div>
<div class="t-box b-debt"><b>My Debtors Owe You</b><div class="amt">₦{{ "{:,.0f}".format(debtors_total) }}</div><div class="words">{{debtors_words}} Naira Only</div></div>
<div class="t-box b-loss"><b>My Losses</b><div class="amt">₦{{ "{:,.0f}".format(losses_total) }}</div><div class="words">{{losses_words}} Naira Only</div></div>
</div>
{% endif %}

{% if session['role']=='owner' %}
<div class="section">⚡ Expedited Alert Requests From Manager - MD/CEO Action Needed</div>
<div class="card">{% for ar in alert_requests %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:12px"><b>{{ar['alert_item']}} - {{ar['alert_type']}} - {{ar['status']}}</b><br><span>From {{ar['created_by']}} on {{ar['date']}}</span><br><span><b>Manager Request / Suggestion:</b> {{ar['manager_message']}}</span><br>{% if ar['owner_remark'] %}<span><b>Your Instruction:</b> {{ar['owner_remark']}}</span><br>{% endif %}{% if ar['status']=='Pending' %}<form method="post" action="/review_alert_request/{{ar['id']}}" style="margin-top:10px"><label>MD/CEO Instruction / Remark - Required</label><textarea name="owner_remark" placeholder="e.g. Approved, go ahead with discount / Rejected, do not dispose - return to supplier / Do this: ..." required></textarea><div class="grid2"><button class="green" name="action" value="Approved">✅ Approve / Go Ahead</button><button style="background:#dc2626" name="action" value="Rejected">❌ Reject / Give Other Instruction</button></div></form>{% elif ar['status']=='Approved' %}<b style="color:#16a34a">✅ Approved - Go Ahead</b>{% elif ar['status']=='Rejected' %}<b style="color:#dc2626">❌ Rejected / Other Instruction Given</b>{% endif %}</div>{% endfor %}{% if not alert_requests %}<p class="muted">No expedited alert requests yet.</p>{% endif %}</div>

<div class="section">📩 Requests From Manager - Click to Approve With Feedback</div>
<div class="card">{% for r in requests %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px"><b>{{r['type']}}: {{r['title']}}</b><br><span>Amount: ₦{{ "{:,.0f}".format(r['amount']) }} • By {{r['created_by']}} • Status: {{r['status']}}</span><br><span class="muted">Items:</span><pre style="white-space:pre-wrap;background:#f8fafc;padding:8px;border-radius:8px">{{r['items']}}</pre><span class="muted">Note: {{r['note']}}</span><br>{% if r['owner_feedback'] %}<b>Your Feedback: {{r['owner_feedback']}}</b><br>{% endif %}{% if r['status']=='Pending' %}<form method="post" action="/approve_request/{{r['id']}}"><label>MD/CEO Feedback / Note to Manager</label><input name="feedback" placeholder="e.g. Approved, buy 10 bags only / Rejected, too expensive" required><div class="grid2"><button class="green" name="action" value="Approved">Approve</button><button style="background:#dc2626" name="action" value="Rejected">Reject</button></div></form>{% endif %}</div>{% endfor %}{% if not requests %}<p class="muted">No requests yet.</p>{% endif %}</div>

<div class="section">📋 History Submitted By Manager - For MD/CEO Review (Approve / Reject With Remark)</div>
<div class="card">{% for s in submissions %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:12px"><b>{{s['period_label']}} - {{s['status']}}</b><br><span>Submitted by {{s['created_by']}} on {{s['date']}}</span><br><span>{{s['summary']}}</span><br><span><b>Manager Remark:</b> {{s['manager_remark']}}</span><br>{% if s['owner_remark'] %}<span><b>MD/CEO Remark:</b> {{s['owner_remark']}}</span><br>{% endif %}{% if s['status']=='Submitted' %}<form method="post" action="/review_submission/{{s['id']}}" style="margin-top:10px"><label>MD/CEO Remark - Required (Approve or Reject)</label><textarea name="owner_remark" placeholder="e.g. Approved, well done / Rejected - Star Beer sales no balance, check again and resubmit" required></textarea><div class="grid2"><button class="green" name="action" value="Approved">✅ Approve - Ends Here</button><button style="background:#dc2626" name="action" value="Rejected">❌ Reject - Send Back To Manager</button></div></form>{% elif s['status']=='Approved' %}<b style="color:#16a34a">✅ Approved by MD/CEO - Closed</b>{% elif s['status']=='Rejected' %}<b style="color:#dc2626">❌ Rejected by MD/CEO - Sent Back To Manager</b>{% endif %}</div>{% endfor %}{% if not submissions %}<p class="muted">No history submitted yet by Manager.</p>{% endif %}</div>
{% endif %}
{% if session['role'] in ['manager','admin'] %}
<div class="section">📩 My Requests To MD/CEO</div>
<div class="card">{% for r in requests %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px"><b>{{r['type']}}: {{r['title']}}</b> - {{r['status']}}<br><pre style="white-space:pre-wrap;background:#f8fafc;padding:8px">{{r['items']}}</pre><span>Note: {{r['note']}}</span><br>{% if r['owner_feedback'] %}<b style="color:#0b5ed7">MD/CEO Feedback: {{r['owner_feedback']}}</b>{% endif %}</div>{% endfor %}{% if not requests %}<p class="muted">No requests yet.</p>{% endif %}</div>

<div class="section">📋 My Submitted Histories To MD/CEO - All Submissions</div>
<div class="card">{% for s in submissions %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px;background:#f8fafc"><b>{{s['period_label']}} - <span style="color:#0b5ed7">{{s['status']}}</span></b> {% if s['status']=='Submitted' %}<span class="submitted-badge">✅ SUBMITTED TO MD/CEO</span>{% endif %}<br><span>{{s['summary']}} • {{s['date']}}</span><br><span><b>My Remark:</b> {{s['manager_remark']}}</span><br>{% if s['owner_remark'] %}<span><b>MD/CEO Remark:</b> {{s['owner_remark']}}</span><br>{% endif %}{% if s['status']=='Approved' %}<b style="color:#16a34a">✅ Approved - Closed</b>{% elif s['status']=='Rejected' %}<b style="color:#dc2626">❌ Rejected - Fix and Resubmit</b>{% elif s['status']=='Submitted' %}<b style="color:#0b5ed7">⏳ Submitted - Waiting For MD/CEO</b>{% endif %}</div>{% endfor %}{% if not submissions %}<p class="muted">You have not submitted any history yet. After you submit, it will show here as SUBMITTED TO MD/CEO.</p>{% endif %}</div>
{% endif %}

{% if session['role'] in ['owner','manager','admin'] %}
<div class="section">📦 Stock / Inventory List - Cost & Selling + Expiry + Min / Max - {{period_label}}</div>
<div class="card" style="padding:0;overflow:hidden"><table><tr><th>Item</th><th>Purchased</th><th>Sold</th><th>Remaining</th><th>Cost</th><th>Selling</th><th>Expiry</th><th>Min</th><th>Max</th><th>Last Sold</th><th>Status</th></tr>
{% for r in combined %}<tr><td><b>{{r['item']}}</b></td><td>{{r['purch_qty']}}</td><td>{{r['sales_qty']}}</td><td><b>{{r['remaining']}}</b></td><td>₦{{ "{:,.0f}".format(r['cost_price']) }}</td><td>₦{{ "{:,.0f}".format(r['selling_price']) }}</td><td>{{r['expiry_date'] or '-'}}</td><td>{{r['min_stock']}}</td><td>{{r['max_stock']}}</td><td>{{r['last_sold'] or '-'}}</td><td>{{r['status']}}</td></tr>{% endfor %}
{% if not combined %}<tr><td colspan="11" style="text-align:center;color:#888">No stock yet</td></tr>{% endif %}
</table></div>
{% endif %}

{% if session['role']=='sales' %}
<div class="section">📦 Available Stock List - Sell From Here (Cost & Selling + Expiry + Min/Max)</div>
<div class="card" style="padding:0;overflow:hidden"><table><tr><th>Item</th><th>Available</th><th>Cost</th><th>Selling</th><th>Expiry</th><th>Min / Max</th><th>Status</th></tr>{% for r in combined %}<tr><td><b>{{r['item']}}</b></td><td>{{r['remaining']}}</td><td>₦{{ "{:,.0f}".format(r['cost_price']) }}</td><td>₦{{ "{:,.0f}".format(r['selling_price']) }}</td><td>{{r['expiry_date'] or '-'}}</td><td>{{r['min_stock']}} / {{r['max_stock']}}</td><td>{{r['status']}}</td></tr>{% endfor %}{% if not combined %}<tr><td colspan="7" style="text-align:center;color:#888">No stock yet - Manager needs to add Purchase first</td></tr>{% endif %}</table></div>
<div class="section">🛒 Add Sale - Salesperson Only</div>
<div class="card"><form method="post" action="/sell"><label>Item</label><select name="item">{% for it in stock_items %}<option value="{{it}}">{{it}}</option>{% endfor %}</select><div class="grid2"><div><label>Qty Sold</label><input name="qty" type="number" step="any" required></div><div><label>Selling Price (₦) Per One</label><input name="price" type="number" step="any" required></div></div><label>Or type new item if not in list</label><input name="item_new" placeholder="Leave blank if you selected above"><button class="green">ADD SALE</button></form></div>
{% endif %}

{% if session['role'] in ['manager','admin'] %}
<div class="section">➕ Add Purchase - Manager / Admin Only (Expiry + Min / Max)</div>
<div class="card"><form method="post" action="/add_purchase"><label>Item Name</label><input name="item" placeholder="e.g. Rice 50kg / Paracetamol / Star Beer" required><div class="grid3"><div><label>Qty Purchased</label><input name="qty" type="number" step="any" required></div><div><label>Cost Price (₦) Per One</label><input name="cost_price" type="number" step="any" required></div><div><label>Selling Price (₦) Per One</label><input name="selling_price" type="number" step="any" required></div></div><div class="grid3"><div><label>Expiry Date (Chemist / Supermarket / Beauty - leave blank if no expiry)</label><input name="expiry_date" type="date"></div><div><label>Minimum Stock / Reorder Level (e.g. 10)</label><input name="min_stock" type="number" step="any" value="0" placeholder="0 = No alert"></div><div><label>Maximum Stock / Do Not Exceed (e.g. 100)</label><input name="max_stock" type="number" step="any" value="0" placeholder="0 = No limit"></div></div><button class="orange">ADD PURCHASE</button></form></div>

<div class="section">🧾 Expenditure / Budget / Salary Request - To MD/CEO For Approval</div>
<div class="card">
<form method="post" action="/add_request" id="reqForm">
<label>Type</label><select name="type" id="reqType" onchange="switchReqType()"><option>Expenditure</option><option>Budget Request</option><option>Salary Schedule</option></select>
<label>Title</label><input name="title" placeholder="e.g. Salary for May / Market run" required>
<div id="expBlock"><label>Itemize - Expenditure / Budget</label><table><tr><th>S/No</th><th>Items</th><th>Qty</th><th>Unit Cost (₦)</th><th>Total Cost / Item (₦)</th><th></th></tr><tbody id="expRows"><tr><td>1</td><td><input name="exp_item" placeholder="e.g. Rice 50kg" required></td><td><input name="exp_qty" type="number" step="any" value="1" oninput="calcExp()"></td><td><input name="exp_unit" type="number" step="any" placeholder="0" oninput="calcExp()"></td><td><input name="exp_total" readonly></td><td><button type="button" class="small" onclick="this.closest('tr').remove();renumberExp();calcExp()">X</button></td></tr></tbody></table><button type="button" class="small blue" onclick="addExpRow()">+ Add Item</button><div style="text-align:right;margin-top:10px"><b>Total Amount: ₦<span id="expGrand">0</span></b></div></div>
<div id="salBlock" style="display:none"><label>Salary Schedule</label><table><tr><th>S/No</th><th>Names & Designation</th><th>Amount (₦)</th><th>Account Number</th><th>Bank Name</th><th></th></tr><tbody id="salRows"><tr><td>1</td><td><input name="sal_name" placeholder="e.g. Chinedu - Salesperson"></td><td><input name="sal_amt" type="number" step="any" placeholder="0" oninput="calcSal()"></td><td><input name="sal_acct" placeholder="0123456789"></td><td><input name="sal_bank" placeholder="e.g. GTB / Access"></td><td><button type="button" class="small" onclick="this.closest('tr').remove();renumberSal();calcSal()">X</button></td></tr></tbody></table><button type="button" class="small blue" onclick="addSalRow()">+ Add Staff</button><div style="text-align:right;margin-top:10px"><b>Total Salary Schedule: ₦<span id="salGrand">0</span></b></div></div>
<label>Note</label><input name="note" placeholder="Extra detail">
<input type="hidden" name="items" id="itemsHidden"><input type="hidden" name="amount" id="amountHidden">
<button onclick="buildRequest()">Send Request To MD/CEO</button>
</form>
</div>
<script>
function switchReqType(){var t=document.getElementById('reqType').value;var isSal=t==='Salary Schedule';document.getElementById('salBlock').style.display=isSal?'block':'none';document.getElementById('expBlock').style.display=isSal?'none':'block';document.querySelectorAll('#expRows input[name="exp_item"]').forEach(e=>e.required=!isSal);document.querySelectorAll('#salRows input[name="sal_name"]').forEach(e=>e.required=isSal);}
function renumberExp(){document.querySelectorAll('#expRows tr').forEach((r,i)=>r.cells[0].innerText=i+1)}
function renumberSal(){document.querySelectorAll('#salRows tr').forEach((r,i)=>r.cells[0].innerText=i+1)}
function addExpRow(){var tb=document.getElementById('expRows');var tr=document.createElement('tr');tr.innerHTML='<td></td><td><input name="exp_item" placeholder="Item"></td><td><input name="exp_qty" type="number" step="any" value="1" oninput="calcExp()"></td><td><input name="exp_unit" type="number" step="any" placeholder="0" oninput="calcExp()"></td><td><input name="exp_total" readonly></td><td><button type="button" class="small" onclick="this.closest(\\'tr\\').remove();renumberExp();calcExp()">X</button></td>';tb.appendChild(tr);renumberExp();}
function addSalRow(){var tb=document.getElementById('salRows');var tr=document.createElement('tr');tr.innerHTML='<td></td><td><input name="sal_name" placeholder="Name - Designation"></td><td><input name="sal_amt" type="number" step="any" placeholder="0" oninput="calcSal()"></td><td><input name="sal_acct" placeholder="Account No"></td><td><input name="sal_bank" placeholder="Bank"></td><td><button type="button" class="small" onclick="this.closest(\\'tr\\').remove();renumberSal();calcSal()">X</button></td>';tb.appendChild(tr);renumberSal();}
function calcExp(){var grand=0;document.querySelectorAll('#expRows tr').forEach(r=>{var q=parseFloat(r.querySelector('[name="exp_qty"]').value||0);var u=parseFloat(r.querySelector('[name="exp_unit"]').value||0);var tot=q*u;r.querySelector('[name="exp_total"]').value=tot.toFixed(0);grand+=tot;});document.getElementById('expGrand').innerText=grand.toLocaleString();return grand;}
function calcSal(){var grand=0;document.querySelectorAll('#salRows tr').forEach(r=>{grand+=parseFloat(r.querySelector('[name="sal_amt"]').value||0);});document.getElementById('salGrand').innerText=grand.toLocaleString();return grand;}
function buildRequest(){var t=document.getElementById('reqType').value;var lines=[];var total=0;if(t==='Salary Schedule'){document.querySelectorAll('#salRows tr').forEach((r,i)=>{var n=r.querySelector('[name="sal_name"]').value||'';var a=parseFloat(r.querySelector('[name="sal_amt"]').value||0);var acct=r.querySelector('[name="sal_acct"]').value||'';var bank=r.querySelector('[name="sal_bank"]').value||'';if(n){lines.push((i+1)+'. '+n+' | Amount: ₦'+a.toLocaleString()+' | Acct: '+acct+' | Bank: '+bank);total+=a;}});lines.push('---');lines.push('TOTAL FOR SCHEDULE: ₦'+total.toLocaleString());}else{document.querySelectorAll('#expRows tr').forEach((r,i)=>{var it=r.querySelector('[name="exp_item"]').value||'';var q=parseFloat(r.querySelector('[name="exp_qty"]').value||0);var u=parseFloat(r.querySelector('[name="exp_unit"]').value||0);var tot=q*u;if(it){lines.push((i+1)+'. '+it+' | Qty: '+q+' | Unit Cost: ₦'+u.toLocaleString()+' | Total: ₦'+tot.toLocaleString());total+=tot;}});lines.push('---');lines.push('TOTAL AMOUNT: ₦'+total.toLocaleString());}document.getElementById('itemsHidden').value=lines.join('\\n');document.getElementById('amountHidden').value=total;}
switchReqType();
</script>
{% endif %}

{% if session['role'] in ['manager','admin'] %}
<div class="section">Sales & Purchases - {{period_label}} - Manager / Admin Only</div>
<div class="card" style="padding:0;overflow:hidden"><table><tr><th>Item</th><th>Purchased</th><th>Sold</th><th>Remaining</th><th>Cost Price</th><th>Selling Price</th><th>Profit</th></tr>
{% for r in combined %}<tr><td><b>{{r['item']}}</b></td><td>{{r['purch_qty']}}</td><td>{{r['sales_qty']}}</td><td><b>{{r['remaining']}}</b></td><td>₦{{ "{:,.0f}".format(r['cost_price']) }}</td><td>₦{{ "{:,.0f}".format(r['selling_price']) }}</td><td style="color:#16a34a;font-weight:800">₦{{ "{:,.0f}".format(r['profit']) }}</td></tr>{% endfor %}
{% if not combined %}<tr><td colspan="7" style="text-align:center;color:#888">No sales / purchases for this period yet</td></tr>{% endif %}
</table></div>
{% endif %}

{% if session['role'] in ['manager','admin'] %}
<div class="section">Expenses - Manager / Admin Only (Direct)</div>
<div class="card"><form method="post" action="/add_expense"><label>Expense Item</label><input name="item" placeholder="e.g. Transport, Rent, NEPA" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Note</label><input name="note" placeholder="Optional note"><button>Add Expense</button></form>
{% for r in expenses %}<div class="row-card"><div><b>{{r['item']}}</b><br><span>{{r['note']}} • Added by {{r['created_by']}}</span></div><b>₦{{r['amount']}}</b></div>{% endfor %}</div>
{% endif %}

{% if session['role'] in ['owner','manager','admin'] %}
<div class="section">Show Full History ({{period_label}}) - Manager / MD/CEO</div>
<div class="card" style="padding:0;overflow:hidden"><table><tr><th>Type</th><th>Item</th><th>Qty</th><th>Cost</th><th>Selling</th><th>Total</th><th>Added By</th></tr>
{% for r in history %}<tr><td><span class="badge">{{r['type']}}</span></td><td>{{r['item']}}</td><td>{{r['qty']}}</td><td>₦{{r['cost']}}</td><td>₦{{r['selling']}}</td><td>₦{{r['total']}}</td><td>{{r['created_by']}} ({{r['created_by_role']}})</td></tr>{% endfor %}
</table>
{% if session['role'] in ['manager','admin'] %}
<div style="padding:14px;border-top:2px solid #0b3d91;margin-top:0">
<label><input type="checkbox" id="reviewCheck" style="width:auto;margin-right:8px" onchange="document.getElementById('submitBtn').disabled=!this.checked"> ✅ I have reviewed this {{period_label}} history - I confirm it is correct</label>
<form method="post" action="/submit_history" style="margin-top:10px">
<input type="hidden" name="period" value="{{period}}">
<input type="hidden" name="period_label" value="{{period_label}}">
<input type="hidden" name="summary" value="Sales ₦{{sales_total}} | Purchases ₦{{purch_total}} | Profit ₦{{profit}} | {{history|length}} records">
<label>Manager Remark - Required Before Submission</label>
<textarea name="manager_remark" placeholder="e.g. I don check Today history - 12 sales, 2 debtors, all correct. No missing item." required></textarea>
<button id="submitBtn" class="blue" disabled>Submit This History To MD/CEO For Review</button>
</form>
<p class="muted" style="margin:8px 0 0">Tick checkbox + write remark, then submit. MD/CEO will see your remark. After submit, it will show at top as SUBMITTED TO MD/CEO.</p>
</div>
{% endif %}
</div>
{% endif %}
{% if session['role']=='sales' %}
<div class="section">My Sales History ({{period_label}}) - My Own Only</div>
<div class="card" style="padding:0;overflow:hidden"><table><tr><th>Item</th><th>Qty</th><th>Selling</th><th>Total</th></tr>
{% for r in history %}{% if r['type']=='SALE' %}<tr><td>{{r['item']}}</td><td>{{r['qty']}}</td><td>₦{{r['selling']}}</td><td>₦{{r['total']}}</td></tr>{% endif %}{% endfor %}
</table></div>
{% endif %}

{% if session['role']=='sales' %}
<div class="section">Debtors - Who Owe You - Salesperson Only - My Own</div>
<div class="card"><form method="post" action="/add_debtor"><label>Customer Name</label><input name="name" required><label>Phone</label><input name="phone" placeholder="080..."><label>Item Bought</label><input name="item" placeholder="What they bought"><label>Amount Owed (₦)</label><input name="amount" type="number" step="any" required><label>Reason - Why Debtor Exists</label><select name="reason" required><option>No Change</option><option>Loyal / Regular Customer</option><option>Failed Transfer</option><option>No Network</option><option>Failed POS</option></select><label>Settlement Timeframe</label><select name="timeframe" required><option>1-3 days</option><option>4-7 days</option><option>7-10 days</option><option>10-14 days</option></select><button>Add Debtor</button></form>
{% for r in debtors %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px"><b>{{r['name']}}</b> - {{r['status']}}<br><span>{{r['item']}} • {{r['phone']}} • Reason: {{r['reason']}} • Timeframe: {{r['timeframe']}}</span><br><span>Total: ₦{{r['amount']}} • Paid: ₦{{r['paid_amount']}} • Remaining: ₦{{r['amount']-r['paid_amount']}}</span>{% if r['status']!='Settled' %}<form method="post" action="/settle_debtor/{{r['id']}}"><label>Amount Paid Now (₦)</label><input name="pay_amount" type="number" step="any" required><label>Is this Full Payment?</label><select name="is_full"><option value="auto">Auto - If Paid = Remaining, mark Settled</option><option value="yes">Yes - Mark as Settled in Full</option><option value="no">No - Partly Paid, Keep Open</option></select><button class="small green">Record Payment</button></form>{% endif %}</div>{% endfor %}</div>
{% endif %}
{% if session['role'] in ['owner','manager','admin'] %}
<div class="section">Debtors - View Only (MD/CEO / Manager cannot add/settle)</div>
<div class="card">{% for r in debtors %}<div class="row-card"><div><b>{{r['name']}}</b><br><span>{{r['item']}} • Reason: {{r['reason']}} • Timeframe: {{r['timeframe']}} • {{r['status']}} • By {{r['created_by']}}</span></div><div><b>₦{{r['amount']}}</b><br><small>Paid: ₦{{r['paid_amount']}} • Remaining: ₦{{r['amount']-r['paid_amount']}}</small></div></div>{% endfor %}{% if not debtors %}<p class="muted">No debtors.</p>{% endif %}</div>
{% endif %}

{% if session['role'] in ['manager','admin'] %}
<div class="section">Creditors - Who You Owe - Manager Only</div>
<div class="card"><form method="post" action="/add_creditor"><label>Supplier Name</label><input name="name" required><label>Phone</label><input name="phone"><label>Item</label><input name="item"><label>Amount Owed (₦)</label><input name="amount" type="number" step="any" required><label>Reason</label><select name="reason" required><option>Credit Purchase</option></select><label>Settlement Timeframe</label><select name="timeframe" required><option>1-3 days</option><option>4-7 days</option><option>7-10 days</option><option>10-14 days</option></select><button>Add Creditor</button></form>
{% for r in creditors %}<div style="border:1px solid #dbeafe;border-radius:12px;padding:12px;margin-bottom:10px"><b>{{r['name']}}</b> - {{r['status']}}<br><span>{{r['item']}} • {{r['phone']}} • Reason: {{r['reason']}} • Timeframe: {{r['timeframe']}}</span><br><span>Total: ₦{{r['amount']}} • Paid: ₦{{r['paid_amount']}} • Remaining: ₦{{r['amount']-r['paid_amount']}}</span>{% if r['status']!='Settled' %}<form method="post" action="/settle_creditor/{{r['id']}}"><label>Amount Paid Now (₦)</label><input name="pay_amount" type="number" step="any" required><label>Is this Full Payment?</label><select name="is_full"><option value="auto">Auto</option><option value="yes">Yes - Settled in Full</option><option value="no">No - Partly Paid</option></select><button class="small green">Record Payment</button></form>{% endif %}</div>{% endfor %}</div>
{% endif %}
{% if session['role'] in ['owner','sales'] %}
<div class="section">Creditors - View Only</div>
<div class="card">{% for r in creditors %}<div class="row-card"><div><b>{{r['name']}}</b><br><span>{{r['item']}} • Reason: {{r['reason']}} • Timeframe: {{r['timeframe']}} • {{r['status']}}</span></div><div>{% if session['role']=='owner' %}<b>₦{{r['amount']}}</b><br><small>Paid: ₦{{r['paid_amount']}} • Remaining: ₦{{r['amount']-r['paid_amount']}}</small>{% else %}<small>View only</small>{% endif %}</div></div>{% endfor %}{% if not creditors %}<p class="muted">No creditors.</p>{% endif %}</div>
{% endif %}

{% if session['role'] in ['manager','admin'] %}
<div class="section">Losses - Manager / Admin</div>
<div class="card"><form method="post" action="/add_loss"><label>Loss Item</label><input name="item" required><label>Amount (₦)</label><input name="amount" type="number" step="any" required><label>Reason</label><select name="reason" required><option>Expired</option><option>Broken Seal</option><option>Damaged</option><option>Lost</option><option>Bad / Inferior Product</option></select><label>Note (optional)</label><input name="note" placeholder="Extra detail"><button>Add Loss</button></form>
{% for r in losses %}<div class="row-card" style="border-left-color:#dc2626"><div><b>{{r['item']}}</b><br><span>Reason: {{r['reason']}} • {{r['note']}} • Added by {{r['created_by']}}</span></div><b>₦{{r['amount']}}</b></div>{% endfor %}</div>
{% endif %}
{% if session['role']=='owner' %}
<div class="section">Losses - View Only</div>
<div class="card">{% for r in losses %}<div class="row-card" style="border-left-color:#dc2626"><div><b>{{r['item']}}</b><br><span>Reason: {{r['reason']}} • {{r['note']}} • By {{r['created_by']}}</span></div><b>₦{{r['amount']}}</b></div>{% endfor %}{% if not losses %}<p class="muted">No losses yet.</p>{% endif %}</div>
{% endif %}
{% if session['role']=='sales' %}
<div class="section">My Losses - My Own Only</div>
<div class="card">{% for r in losses %}<div class="row-card" style="border-left-color:#dc2626"><div><b>{{r['item']}}</b><br><span>Reason: {{r['reason']}} • {{r['note']}}</span></div><b>₦{{r['amount']}}</b></div>{% endfor %}{% if not losses %}<p class="muted">No losses recorded for you yet.</p>{% endif %}</div>
{% endif %}
</div>
""" + FOOTER

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET","POST"])
def login():
    conn = get_db()
    shops = conn.execute("SELECT * FROM shops").fetchall()
    conn.close()
    if request.method == "POST":
        session.clear()
        shop_id = request.form['shop_id']
        u = request.form['username']
        p = request.form['password']
        conn = get_db()
        shop_check = conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()
        if shop_check and shop_check['is_active'] is not None and shop_check['is_active'] == 0:
            conn.close()
            return "This shop is suspended - subscription expired. Contact Super Admin. <a href='/login'>Go Back</a>"
        user = conn.execute("SELECT * FROM users WHERE shop_id=? AND username=? AND password=?", (shop_id, u, p)).fetchone()
        if user:
            session['shop_id'] = int(shop_id)
            session['username'] = user['username']
            session['role'] = user['role']
            conn.close()
            return redirect("/shop")
        conn.close()
        return "Wrong login. <a href='/login'>Try again</a>"
    return render_template_string(LOGIN_HTML, shops=shops)

@app.route("/super_login", methods=["GET","POST"])
def super_login():
    if request.method == "POST":
        if request.form['username'] == "superadmin" and request.form['password'] == "super123":
            session['role'] = "superadmin"
            session['username'] = "superadmin"
            return redirect("/super")
        return "Wrong super admin. <a href='/super_login'>Try again</a>"
    return render_template_string(SUPER_LOGIN_HTML)

@app.route("/super")
def super_page():
    if session.get("role") != "superadmin":
        return redirect("/super_login")
    conn = get_db()
    shops = conn.execute("SELECT * FROM shops").fetchall()
    enriched = []
    total_activity = 0
    total_staff = 0
    for s in shops:
        sid = s['id']
        users = conn.execute("SELECT username, role FROM users WHERE shop_id=?", (sid,)).fetchall()
        txt = ", ".join([f"{u['username']} ({display_role(u['role'])})" for u in users]) or "No staff yet"
        def cnt(tbl):
            r = conn.execute(f"SELECT COUNT(*) as c FROM {tbl} WHERE shop_id=?", (sid,)).fetchone()
            return r['c'] if r else 0
        sales_c = cnt("sales"); purch_c = cnt("purchases"); debt_c = cnt("debtors"); cred_c = cnt("creditors"); loss_c = cnt("losses"); exp_c = cnt("expenses"); req_c = cnt("requests"); sub_c = cnt("submissions"); alert_c = cnt("alert_requests")
        activity = sales_c + purch_c + debt_c + cred_c + loss_c + exp_c + req_c + sub_c + alert_c
        total_activity += activity
        total_staff += len(users)
        d = dict(s)
        d['users'] = txt
        d['staff_count'] = len(users)
        d['sales_count'] = sales_c
        d['purch_count'] = purch_c
        d['debtors_count'] = debt_c
        d['requests_count'] = req_c
        d['activity'] = activity
        d['traffic_pct'] = 0
        if d.get('is_active') is None:
            d['is_active'] = 1
        enriched.append(d)
    if total_activity > 0:
        for d in enriched:
            d['traffic_pct'] = round((d['activity'] / total_activity) * 100, 1)
    enriched_sorted = sorted(enriched, key=lambda x: x['activity'], reverse=True)
    conn.close()
    return render_template_string(SUPER_HTML, shops=enriched, shops_sorted=enriched_sorted, total_shops=len(enriched), total_activity=total_activity, total_staff=total_staff)

@app.route("/create_shop", methods=["POST"])
def create_shop():
    if session.get("role") != "superadmin":
        return redirect("/super_login")
    conn = get_db()
    conn.execute("INSERT INTO shops (name, is_active) VALUES (?,1)", (request.form['name'],))
    conn.commit()
    conn.close()
    return redirect("/super")

@app.route("/add_staff/<int:shop_id>", methods=["POST"])
def add_staff(shop_id):
    if session.get("role") != "superadmin":
        return redirect("/super_login")
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (shop_id, username, password, role, name) VALUES (?,?,?,?,?)", (shop_id, request.form['username'], request.form['password'], request.form['role'], request.form.get('name','')))
        conn.commit()
    except:
        conn.close()
        return "Username already exists. Use different username e.g. manager2. <a href='/super'>Go Back</a>"
    conn.close()
    return redirect("/super")

@app.route("/toggle_shop/<int:shop_id>", methods=["POST"])
def toggle_shop(shop_id):
    if session.get("role") != "superadmin":
        return redirect("/super_login")
    conn = get_db()
    shop = conn.execute("SELECT is_active FROM shops WHERE id=?", (shop_id,)).fetchone()
    current = shop['is_active'] if shop and shop['is_active'] is not None else 1
    new_val = 0 if current == 1 else 1
    conn.execute("UPDATE shops SET is_active=? WHERE id=?", (new_val, shop_id))
    conn.commit()
    conn.close()
    return redirect("/super")

@app.route("/delete_shop/<int:shop_id>", methods=["POST"])
def delete_shop(shop_id):
    if session.get("role") != "superadmin":
        return redirect("/super_login")
    conn = get_db()
    conn.execute("DELETE FROM shops WHERE id=?", (shop_id,))
    conn.execute("DELETE FROM users WHERE shop_id=?", (shop_id,))
    conn.commit()
    conn.close()
    return redirect("/super")

def normalize_sales_purch(rows):
    out = []
    for r in rows:
        d = dict(r)
        qty = float(safe(r,"qty","quantity") or 0)
        price = float(safe(r,"price","selling_price","unit_price") or 0)
        cost = float(safe(r,"cost_price","cost") or 0)
        selling = float(safe(r,"selling_price","price") or price)
        if selling == 0:
            selling = price
        total = float(safe(r,"total") or qty * selling)
        out.append({"item": d.get("item") or d.get("name") or "", "qty": qty, "price": selling, "cost_price": cost, "selling_price": selling, "total": total, "created_by": d.get("created_by") or "", "created_by_role": d.get("created_by_role") or "", "date": d.get("date") or "", "expiry_date": d.get("expiry_date") or "", "min_stock": float(safe(r,"min_stock") or 0), "max_stock": float(safe(r,"max_stock") or 0)})
    return out

def period_range(period):
    t = datetime.date.today()
    if period == 'today':
        return t.isoformat(), t.isoformat(), "Today"
    if period == 'week':
        s = t - datetime.timedelta(days=t.weekday())
        return s.isoformat(), t.isoformat(), "This Week"
    if period == 'month':
        return t.replace(day=1).isoformat(), t.isoformat(), "This Month"
    if period == 'quarter':
        q = (t.month-1)//3
        s = t.replace(month=q*3+1, day=1)
        return s.isoformat(), t.isoformat(), "This Quarter"
    if period == 'year':
        return t.replace(month=1, day=1).isoformat(), t.isoformat(), "This Year"
    return "0000-01-01", "9999-12-31", "All Time"

@app.route("/shop")
def shop():
    if 'shop_id' not in session:
        return redirect("/login")
    period = request.args.get('period','today')
    start, end, period_label = period_range(period)
    just_submitted = request.args.get('submitted') == '1'
    alert_submitted = request.args.get('alert_submitted') == '1'
    conn = get_db()
    shop = conn.execute("SELECT * FROM shops WHERE id=?", (session['shop_id'],)).fetchone()
    if shop and shop['is_active'] is not None and shop['is_active'] == 0:
        conn.close()
        session.clear()
        return "This shop is suspended - subscription expired. Contact Super Admin. <a href='/login'>Go Back</a>"
    def fetch(tbl):
        return conn.execute(f"SELECT * FROM {tbl} WHERE shop_id=?", (session['shop_id'],)).fetchall()
    sales_raw = fetch("sales")
    purch_raw = fetch("purchases")
    debtors_raw = fetch("debtors")
    creditors_raw = fetch("creditors")
    losses_raw = fetch("losses")
    expenses_raw = fetch("expenses")
    requests_raw = fetch("requests")
    submissions_raw = fetch("submissions")
    alert_requests_raw = fetch("alert_requests")
    conn.close()
    role = session.get('role')
    me = session.get('username')
    def role_filter(rows):
        if role == 'sales':
            return [r for r in rows if dict(r).get('created_by') == me]
        return rows
    sales_raw = role_filter(sales_raw)
    debtors_raw = role_filter(debtors_raw)
    losses_raw = role_filter(losses_raw) if role == 'sales' else losses_raw
    if role == 'sales':
        purch_raw_display = []
        expenses_raw = []
    else:
        purch_raw_display = purch_raw
    def period_filter(rows):
        if period == 'all':
            return rows
        out = []
        for r in rows:
            d = dict(r).get('date') or today_str()
            if start <= d <= end:
                out.append(r)
        return out
    sales_raw_p = period_filter(sales_raw)
    purch_raw_p = period_filter(purch_raw_display) if role != 'sales' else period_filter(purch_raw)
    debtors_raw_p = period_filter(debtors_raw)
    creditors_raw_p = period_filter(creditors_raw)
    losses_raw_p = period_filter(losses_raw)
    expenses_raw_p = period_filter(expenses_raw)
    sales = normalize_sales_purch(sales_raw_p)
    purchases = normalize_sales_purch(purch_raw_p)
    def norm_other(rows):
        o = []
        for r in rows:
            d = dict(r)
            o.append({"id": d.get("id"), "name": d.get("name") or d.get("item") or "", "item": d.get("item") or d.get("name") or "", "amount": float(safe(r,"amount","total","price") or 0), "paid_amount": float(safe(r,"paid_amount") or 0), "phone": d.get("phone") or "", "note": d.get("note") or "", "reason": d.get("reason") or "", "timeframe": d.get("timeframe") or "", "status": d.get("status") or "Owing", "created_by": d.get("created_by") or "", "created_by_role": d.get("created_by_role") or "", "date": d.get("date") or ""})
        return o
    def norm_req(rows):
        o = []
        for r in rows:
            d = dict(r)
            o.append({"id": d.get("id"), "type": d.get("type") or "Expenditure", "title": d.get("title") or d.get("item") or "", "amount": float(safe(r,"amount") or 0), "note": d.get("note") or "", "items": d.get("items") or "", "status": d.get("status") or "Pending", "owner_feedback": d.get("owner_feedback") or "", "created_by": d.get("created_by") or "", "created_by_role": d.get("created_by_role") or ""})
        return o
    def norm_sub(rows):
        o = []
        for r in rows:
            d = dict(r)
            o.append({"id": d.get("id"), "period": d.get("period") or "", "period_label": d.get("period_label") or "", "summary": d.get("summary") or "", "status": d.get("status") or "Submitted", "manager_remark": d.get("manager_remark") or "", "owner_remark": d.get("owner_remark") or "", "created_by": d.get("created_by") or "", "date": d.get("date") or ""})
        return o
    def norm_alert(rows):
        o = []
        for r in rows:
            d = dict(r)
            o.append({"id": d.get("id"), "alert_item": d.get("alert_item") or "", "alert_type": d.get("alert_type") or "", "manager_message": d.get("manager_message") or d.get("manager_remark") or "", "status": d.get("status") or "Pending", "owner_remark": d.get("owner_remark") or "", "created_by": d.get("created_by") or "", "date": d.get("date") or ""})
        return o
    debtors = norm_other(debtors_raw_p)
    creditors = norm_other(creditors_raw_p)
    losses = norm_other(losses_raw_p)
    expenses = norm_other(expenses_raw_p)
    requests_list = norm_req(requests_raw)
    submissions = norm_sub(submissions_raw)
    alert_requests = norm_alert(alert_requests_raw)
    submissions = sorted(submissions, key=lambda x: x['id'], reverse=True)
    alert_requests = sorted(alert_requests, key=lambda x: x['id'], reverse=True)
    if role in ('manager','admin'):
        requests_list = [r for r in requests_list if r['created_by'] == me]
        submissions = [s for s in submissions if s['created_by'] == me]
        alert_requests = [a for a in alert_requests if a['created_by'] == me]
    sales_total = sum([s['qty']*s['selling_price'] for s in sales])
    sales_qty = sum([s['qty'] for s in sales])
    purch_total = sum([s['qty']*s['cost_price'] if s['cost_price'] else s['qty']*s['selling_price'] for s in purchases])
    debtors_total = sum([(s['amount']-s['paid_amount']) for s in debtors if s['status'] != 'Settled'])
    creditors_total = sum([(s['amount']-s['paid_amount']) for s in creditors if s['status'] != 'Settled'])
    losses_total = sum([s['amount'] for s in losses])
    expenses_total = sum([s['amount'] for s in expenses])
    conn2 = get_db()
    all_purch_raw = conn2.execute("SELECT * FROM purchases WHERE shop_id=?", (session['shop_id'],)).fetchall()
    conn2.close()
    all_purch = normalize_sales_purch(all_purch_raw)
    cost_map = {}
    for p in all_purch:
        cost_map[p['item']] = p['cost_price']
    conn3 = get_db()
    all_sales_raw = conn3.execute("SELECT * FROM sales WHERE shop_id=?", (session['shop_id'],)).fetchall()
    conn3.close()
    last_sold_map = {}
    for r in all_sales_raw:
        d = dict(r)
        it = d.get("item") or ""
        dt = d.get("date") or ""
        if it and (it not in last_sold_map or dt > last_sold_map[it]):
            last_sold_map[it] = dt
    profit = sum([(s['selling_price']-cost_map.get(s['item'], s['cost_price'] or s['selling_price']*0.7))*s['qty'] for s in sales])
    if profit < 0:
        profit = 0
    stock = sum([p['qty']*p['cost_price'] for p in purchases]) - sum([s['qty']*cost_map.get(s['item'], s['cost_price']) for s in sales])
    if stock < 0:
        stock = 0
    if role == 'sales':
        cmap_src_purch = all_purch
        cmap_src_sales = sales
    else:
        cmap_src_purch = purchases
        cmap_src_sales = sales
    cmap = {}
    for p in cmap_src_purch:
        cmap.setdefault(p['item'], {"item":p['item'],"purch_qty":0,"sales_qty":0,"cost_price":p['cost_price'],"selling_price":p['selling_price'],"created_by":p['created_by'],"profit":0,"expiry_date":p['expiry_date'],"min_stock":p['min_stock'],"max_stock":p['max_stock'],"last_sold":last_sold_map.get(p['item'],""),"status":"OK"})
        cmap[p['item']]["purch_qty"] += p['qty']
        cmap[p['item']]["cost_price"] = p['cost_price']
        cmap[p['item']]["selling_price"] = p['selling_price']
        if p['expiry_date']:
            cmap[p['item']]["expiry_date"] = p['expiry_date']
        if p['min_stock']:
            cmap[p['item']]["min_stock"] = p['min_stock']
        if p['max_stock']:
            cmap[p['item']]["max_stock"] = p['max_stock']
    for s in cmap_src_sales:
        cmap.setdefault(s['item'], {"item":s['item'],"purch_qty":0,"sales_qty":0,"cost_price":s['cost_price'],"selling_price":s['selling_price'],"created_by":s['created_by'],"profit":0,"expiry_date":"","min_stock":0,"max_stock":0,"last_sold":last_sold_map.get(s['item'],""),"status":"OK"})
        cmap[s['item']]["sales_qty"] += s['qty']
        cmap[s['item']]["selling_price"] = s['selling_price']
        cmap[s['item']]["profit"] += (s['selling_price']-cmap[s['item']]["cost_price"])*s['qty']
        cmap[s['item']]["last_sold"] = last_sold_map.get(s['item'],"")
    combined = []
    today_d = datetime.date.today()
    alerts_expired = []
    alerts_expiring = []
    alerts_low = []
    alerts_over = []
    alerts_slow = []
    for v in cmap.values():
        v["remaining"] = v["purch_qty"]-v["sales_qty"]
        v["last_sold"] = last_sold_map.get(v["item"],"")
        status = "OK"
        exp = v.get("expiry_date") or ""
        if exp:
            try:
                exp_d = datetime.date.fromisoformat(exp)
                if exp_d < today_d:
                    status = "EXPIRED"
                    alerts_expired.append(v)
                elif (exp_d - today_d).days <= 30:
                    status = "EXPIRING SOON"
                    alerts_expiring.append(v)
            except:
                pass
        if status in ("OK","EXPIRING SOON"):
            if v.get("max_stock",0) and v["remaining"] > v["max_stock"]:
                if status == "OK":
                    status = "OVERSTOCK"
                alerts_over.append(v)
            elif v.get("min_stock",0) and v["remaining"] <= v["min_stock"] and v["remaining"] >= 0:
                if status == "OK":
                    status = "LOW - REORDER"
                alerts_low.append(v)
        if status == "OK" and v["remaining"] > 0:
            last = v.get("last_sold") or ""
            is_slow = False
            if not last:
                is_slow = True
            else:
                try:
                    last_d = datetime.date.fromisoformat(last)
                    if (today_d - last_d).days >= 90:
                        is_slow = True
                except:
                    pass
            if is_slow:
                status = "SLOW-MOVING"
                alerts_slow.append(v)
        v["status"] = status
        combined.append(v)
    if role == 'sales':
        purch_total = 0
        stock = 0
        creditors_total = 0
        expenses_total = 0
    history = []
    if role != 'sales':
        for s in purchases:
            history.append({"type":"PURCHASE","item":s['item'],"qty":s['qty'],"cost":s['cost_price'],"selling":s['selling_price'],"total":s['qty']*s['cost_price'],"created_by":s['created_by'],"created_by_role":display_role(s['created_by_role'])})
    for s in sales:
        history.append({"type":"SALE","item":s['item'],"qty":s['qty'],"cost":cost_map.get(s['item'], s['cost_price']),"selling":s['selling_price'],"total":s['qty']*s['selling_price'],"created_by":s['created_by'],"created_by_role":display_role(s['created_by_role'])})
    if role == 'sales':
        stock_items = sorted(list(set([c['item'] for c in combined]))) or ["General"]
    else:
        stock_items = sorted(list(set([p['item'] for p in purchases] + [s['item'] for s in sales]))) or ["General"]
    top_map = {}
    for s in sales:
        top_map.setdefault(s['item'], {"item":s['item'],"sales_qty":0,"sales_total":0,"profit":0})
        top_map[s['item']]["sales_qty"] += s['qty']
        top_map[s['item']]["sales_total"] += s['qty']*s['selling_price']
        top_map[s['item']]["profit"] += (s['selling_price']-cost_map.get(s['item'], s['cost_price']))*s['qty']
    top_products = sorted(top_map.values(), key=lambda x: x['profit'], reverse=True)[:5]
    profit_by_user = {}
    for s in sales:
        p = (s['selling_price']-cost_map.get(s['item'], s['cost_price']))*s['qty']
        profit_by_user[s['created_by']] = profit_by_user.get(s['created_by'],0)+p
    today = today_str()
    return render_template_string(SHOP_HTML, shop=shop, sales=sales, purchases=purchases, debtors=debtors, creditors=creditors, losses=losses, expenses=expenses, requests=requests_list, submissions=submissions, alert_requests=alert_requests, session=session, display_role=display_role(role), today=today, period=period, period_label=period_label, combined=combined, history=history, stock_items=stock_items, top_products=top_products, profit_by_user=profit_by_user, alerts_expired=alerts_expired, alerts_expiring=alerts_expiring, alerts_low=alerts_low, alerts_over=alerts_over, alerts_slow=alerts_slow, just_submitted=just_submitted, alert_submitted=alert_submitted,
        sales_total=sales_total, sales_qty=int(sales_qty), purch_total=purch_total, debtors_total=debtors_total, creditors_total=creditors_total, losses_total=losses_total, expenses_total=expenses_total, profit=profit, stock=stock,
        sales_words=num_to_words(sales_total), purch_words=num_to_words(purch_total), debtors_words=num_to_words(debtors_total), creditors_words=num_to_words(creditors_total), losses_words=num_to_words(losses_total), profit_words=num_to_words(profit), stock_words=num_to_words(stock), net_words=num_to_words(max(0, profit-losses_total-expenses_total)))

def add_generic(table, fields):
    if 'shop_id' not in session:
        return redirect("/login")
    if is_owner():
        return blocked_msg("MD/CEO cannot post to records. View only.")
    conn = get_db()
    vals = [request.form.get(f) or "" for f in fields]
    cols = ", ".join(fields)
    qs = ", ".join(["?"]*len(fields))
    conn.execute(f"INSERT INTO {table} (shop_id, {cols}, created_by, created_by_role, date) VALUES (?, {qs}, ?, ?, ?)", (session['shop_id'], *vals, session.get("username",""), session.get("role",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/sell", methods=["POST"])
def sell():
    if 'shop_id' not in session:
        return redirect("/login")
    if session.get('role') != 'sales':
        return blocked_msg("Only Salesperson can post Sales.")
    item = request.form.get("item_new") or request.form.get("item") or ""
    qty = request.form.get("qty") or "0"
    price = request.form.get("price") or "0"
    conn = get_db()
    row = conn.execute("SELECT expiry_date FROM purchases WHERE shop_id=? AND item=? ORDER BY id DESC LIMIT 1", (session['shop_id'], item)).fetchone()
    if row and row['expiry_date']:
        try:
            if datetime.date.fromisoformat(row['expiry_date']) < datetime.date.today():
                conn.close()
                return "⛔ This item is EXPIRED - DO NOT SELL. Contact Manager. <a href='/shop'>Go Back</a>"
        except:
            pass
    conn.execute("INSERT INTO sales (shop_id, item, qty, price, selling_price, total, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?)", (session['shop_id'], item, qty, price, price, float(qty or 0)*float(price or 0), session.get("username",""), session.get("role",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/add_purchase", methods=["POST"])
def add_purchase():
    if 'shop_id' not in session:
        return redirect("/login")
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager / Admin can post Purchases.")
    conn = get_db()
    qty = request.form.get("qty") or "0"
    cost = request.form.get("cost_price") or "0"
    sellp = request.form.get("selling_price") or "0"
    expiry = request.form.get("expiry_date") or ""
    min_stock = request.form.get("min_stock") or "0"
    max_stock = request.form.get("max_stock") or "0"
    conn.execute("INSERT INTO purchases (shop_id, item, qty, price, cost_price, selling_price, total, expiry_date, min_stock, max_stock, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (session['shop_id'], request.form.get("item"), qty, cost, cost, sellp, float(qty or 0)*float(cost or 0), expiry, min_stock, max_stock, session.get("username",""), session.get("role",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/add_debtor", methods=["POST"])
def add_debtor():
    if session.get('role') != 'sales':
        return blocked_msg("Only Salesperson can add Debtors.")
    return add_generic("debtors", ["name","phone","item","amount","reason","timeframe"])

@app.route("/add_creditor", methods=["POST"])
def add_creditor():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager / Admin can add Creditors.")
    return add_generic("creditors", ["name","phone","item","amount","reason","timeframe"])

@app.route("/add_loss", methods=["POST"])
def add_loss():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager / Admin can post Loss.")
    return add_generic("losses", ["item","amount","reason","note"])

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager / Admin can post Expense.")
    return add_generic("expenses", ["item","amount","note"])

@app.route("/add_request", methods=["POST"])
def add_request():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager / Admin can send Requests to MD/CEO.")
    items = request.form.get("items") or ""
    amt_raw = request.form.get("amount") or ""
    if not amt_raw:
        total = 0
        try:
            for line in items.splitlines():
                if "-" in line:
                    try:
                        total += float(line.rsplit("-",1)[1].strip().replace(",","").replace("₦",""))
                    except:
                        pass
            amt_raw = str(total)
        except:
            amt_raw = "0"
    conn = get_db()
    conn.execute("INSERT INTO requests (shop_id, type, title, amount, note, items, status, created_by, created_by_role, date) VALUES (?,?,?,?,?,?,?,?,?,?)", (session['shop_id'], request.form.get("type"), request.form.get("title"), amt_raw or 0, request.form.get("note") or "", items, "Pending", session.get("username",""), session.get("role",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/submit_history", methods=["POST"])
def submit_history():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager can submit history.")
    conn = get_db()
    conn.execute("INSERT INTO submissions (shop_id, period, period_label, summary, status, manager_remark, created_by, date) VALUES (?,?,?,?,?,?,?,?)", (session['shop_id'], request.form.get("period") or "", request.form.get("period_label") or "", request.form.get("summary") or "", "Submitted", request.form.get("manager_remark") or "", session.get("username",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop?submitted=1&period=" + (request.form.get("period") or "today"))

@app.route("/submit_alert_request", methods=["POST"])
def submit_alert_request():
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager can submit expedited alert request.")
    conn = get_db()
    conn.execute("INSERT INTO alert_requests (shop_id, alert_item, alert_type, manager_message, status, created_by, date) VALUES (?,?,?,?,?,?,?)", (session['shop_id'], request.form.get("alert_item") or "", request.form.get("alert_type") or "", request.form.get("manager_message") or "", "Pending", session.get("username",""), today_str()))
    conn.commit()
    conn.close()
    return redirect("/shop?alert_submitted=1")

@app.route("/review_alert_request/<int:req_id>", methods=["POST"])
def review_alert_request(req_id):
    if not is_owner():
        return blocked_msg("Only MD/CEO can review expedited requests.")
    action = request.form.get("action") or "Approved"
    owner_remark = request.form.get("owner_remark") or ""
    status = "Approved" if action == "Approved" else "Rejected"
    conn = get_db()
    conn.execute("UPDATE alert_requests SET status=?, owner_remark=? WHERE id=? AND shop_id=?", (status, owner_remark, req_id, session['shop_id']))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/review_submission/<int:sub_id>", methods=["POST"])
def review_submission(sub_id):
    if not is_owner():
        return blocked_msg("Only MD/CEO can review submissions.")
    action = request.form.get("action") or "Approved"
    owner_remark = request.form.get("owner_remark") or ""
    status = "Approved" if action == "Approved" else "Rejected"
    conn = get_db()
    conn.execute("UPDATE submissions SET status=?, owner_remark=? WHERE id=? AND shop_id=?", (status, owner_remark, sub_id, session['shop_id']))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/approve_request/<int:req_id>", methods=["POST"])
def approve_request(req_id):
    if not is_owner():
        return blocked_msg("Only MD/CEO can approve.")
    action = request.form.get("action") or "Approved"
    feedback = request.form.get("feedback") or ""
    conn = get_db()
    conn.execute("UPDATE requests SET status=?, owner_feedback=? WHERE id=? AND shop_id=?", (action, feedback, req_id, session['shop_id']))
    conn.commit()
    conn.close()
    return redirect("/shop")

def do_settle(table, rid):
    pay = float(request.form.get("pay_amount") or 0)
    is_full = request.form.get("is_full") or "auto"
    conn = get_db()
    row = conn.execute(f"SELECT * FROM {table} WHERE id=? AND shop_id=?", (rid, session['shop_id'])).fetchone()
    if not row:
        conn.close()
        return redirect("/shop")
    total = float(row['amount'] or 0)
    paid = float(row['paid_amount'] or 0)
    new_paid = paid + pay
    remaining = total - new_paid
    if is_full == "yes" or (is_full == "auto" and remaining <= 0.01):
        status = "Settled"
        new_paid = total
    elif is_full == "no":
        status = "Partly Paid"
    else:
        status = "Partly Paid" if remaining > 0.01 else "Settled"
    conn.execute(f"UPDATE {table} SET paid_amount=?, status=? WHERE id=?", (new_paid, status, rid))
    conn.commit()
    conn.close()
    return redirect("/shop")

@app.route("/settle_debtor/<int:rid>", methods=["POST"])
def settle_debtor(rid):
    if session.get('role') != 'sales':
        return blocked_msg("Only Salesperson can settle Debtors.")
    return do_settle("debtors", rid)

@app.route("/settle_creditor/<int:rid>", methods=["POST"])
def settle_creditor(rid):
    if session.get('role') not in ('manager','admin'):
        return blocked_msg("Only Manager can settle Creditors.")
    return do_settle("creditors", rid)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)

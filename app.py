import sqlite3, os, json, datetime, hashlib
from flask import Flask, request, redirect, session, g, render_template_string, url_for
app = Flask(__name__)
app.secret_key = "omeyi-v11-secret-2026"
DB = "omeyi.db"

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = db()
    c.execute("CREATE TABLE IF NOT EXISTS shops(id INTEGER PRIMARY KEY, name TEXT, status TEXT DEFAULT 'on', sub_end TEXT, sub_paid TEXT, created TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, role TEXT, phone TEXT, pin TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, cost REAL, price REAL, qty REAL, expiry TEXT, low_level REAL DEFAULT 5)")
    c.execute("CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, product TEXT, qty REAL, amount REAL, cost REAL, date TEXT, created TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS debtors(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, name TEXT, amount REAL, reason TEXT, due_date TEXT, status TEXT DEFAULT 'Open', date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS creditors(id INTEGER PRIMARY KEY, shop_id INTEGER, name TEXT, amount REAL, condition TEXT, due_date TEXT, status TEXT DEFAULT 'Open', date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, title TEXT, amount REAL, category TEXT, date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, date TEXT, opening REAL, closing REAL, sales REAL, purchases REAL, expenditure REAL, profit REAL, bad_debt REAL, debtors_amt REAL, creditors_amt REAL, note TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, type TEXT, title TEXT, amount REAL, status TEXT DEFAULT 'Pending', date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS traffic(id INTEGER PRIMARY KEY, shop_id INTEGER, user_id INTEGER, page TEXT, date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, shop_id INTEGER, md_phone TEXT, mgr_phone TEXT, ceo_phone TEXT)")
    # seed
    if c.execute("SELECT count(*) FROM shops").fetchone()[0]==0:
        c.execute("INSERT INTO shops(name,sub_end,sub_paid,created) VALUES('Omeyi Demo','2026-12-31','2026-11-24','2026-11-24')")
        c.execute("INSERT INTO users(shop_id,name,role,phone,pin) VALUES(1,'Super Admin','superadmin','08000000000','1234')")
        c.execute("INSERT INTO users(shop_id,name,role,phone,pin) VALUES(1,'MD Demo','md','08000000001','1234')")
        c.execute("INSERT INTO users(shop_id,name,role,phone,pin) VALUES(1,'Manager Demo','manager','08000000002','1234')")
        c.execute("INSERT INTO users(shop_id,name,role,phone,pin) VALUES(1,'Sales Demo','sales','08000000003','1234')")
        c.execute("INSERT INTO products(shop_id,name,cost,price,qty,expiry) VALUES(1,'Rice 50kg',40000,48000,20,'2027-01-01')")
        c.execute("INSERT INTO products(shop_id,name,cost,price,qty,expiry) VALUES(1,'Oil 25L',25000,32000,15,'2027-01-01')")
    c.commit()

with app.app_context():
    init()

def today_str():
    return datetime.date.today().isoformat()

def parse_period():
    preset = request.args.get("preset","All")
    s = request.args.get("start","")
    e = request.args.get("end","")
    today = datetime.date.today()
    if s and e:
        return s, e, "Custom"
    if preset=="Today":
        d=today.isoformat(); return d,d,"Today"
    if preset=="Yesterday":
        d=(today-datetime.timedelta(days=1)).isoformat(); return d,d,"Yesterday"
    if preset=="Last 7 Days":
        return (today-datetime.timedelta(days=6)).isoformat(), today.isoformat(), "Last 7 Days"
    if preset=="Last 30 Days":
        return (today-datetime.timedelta(days=29)).isoformat(), today.isoformat(), "Last 30 Days"
    if preset=="Last Quarter":
        return (today-datetime.timedelta(days=90)).isoformat(), today.isoformat(), "Last Quarter"
    if preset=="Last Year":
        return (today-datetime.timedelta(days=365)).isoformat(), today.isoformat(), "Last Year"
    if preset=="This Month":
        return today.replace(day=1).isoformat(), today.isoformat(), "This Month"
    return "2000-01-01", today.isoformat(), "All Time"

def period_bar():
    s,e,label = parse_period()
    html = "<div style='background:#FFF3E0;border:1px solid #FFB74D;padding:12px;border-radius:12px;margin-bottom:12px'>"
    html += "<b>Period: "+label+" | "+s+" to "+e+"</b><br><form method='get' style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'>"
    html += "Start <input type='date' name='start' value='"+s+"'> End <input type='date' name='end' value='"+e+"'>"
    html += "<button>Filter by Calendar</button></form>"
    html += "<div style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'>"
    for p in ["Today","Yesterday","Last 7 Days","Last 30 Days","Last Quarter","Last Year","All Time"]:
        html += "<a href='?preset="+p+"' style='background:#FF9800;color:#fff;padding:6px 10px;border-radius:20px;text-decoration:none;font-size:13px'>"+p+"</a>"
    html += "</div></div>"
    return html

def sub_alert(shop_id):
    c=db()
    r=c.execute("SELECT * FROM shops WHERE id=?",(shop_id,)).fetchone()
    if not r or not r["sub_end"]: return ""
    try:
        end=datetime.date.fromisoformat(r["sub_end"])
        left=(end-datetime.date.today()).days
    except: return ""
    if left<0:
        return "<div style='background:#FFCDD2;padding:12px;border-radius:10px'><b>SUBSCRIPTION EXPIRED!</b> Please renew immediately.</div>"
    if left<=3:
        return "<div style='background:#FFCDD2;padding:12px;border-radius:10px'><b>URGENT: Subscription expires in "+str(left)+" day(s) - "+r["sub_end"]+"</b> - Please renew now. Alert sent to MD/CEO & Manager everyday.</div>"
    return "<div style='background:#E8F5E9;padding:10px;border-radius:10px'>Subscription active - <b>"+str(left)+" days left</b> - Expires "+r["sub_end"]+"</div>"

def top(t,s=""):
    return "<div style='background:#111;color:#fff;padding:16px;border-radius:0 0 16px 16px'><p style='color:#FF9800;margin:0;font-weight:800'>Omeyi</p><h1 style='margin:4px 0'>"+t+"</h1><p style='opacity:.8'>"+s+"</p></div><div style='padding:14px;max-width:900px;margin:auto'>"

def bottom():
    return "</div><div style='text-align:center;padding:20px;opacity:.6'>Omeyi V11</div>"

def card(title,val,sub=""):
    return "<div style='background:#fff;border:1px solid #eee;border-radius:12px;padding:12px;flex:1;min-width:140px'><small>"+title+"</small><h2 style='margin:4px 0'>"+str(val)+"</h2><small>"+sub+"</small></div>"

def log_traffic(shop_id,page):
    try:
        c=db(); c.execute("INSERT INTO traffic(shop_id,user_id,page,date) VALUES(?,?,?,?)",(shop_id,session.get("uid",0),page,today_str())); c.commit()
    except: pass

@app.route("/", methods=["GET","POST"])
def login():
    c=db()
    shops=c.execute("SELECT * FROM shops WHERE status='on'").fetchall()
    if request.method=="POST":
        shop_id=request.form.get("shop_id")
        pin=request.form.get("pin")
        u=c.execute("SELECT * FROM users WHERE shop_id=? AND pin=?",(shop_id,pin)).fetchone()
        if u:
            session["uid"]=u["id"]; session["shop"]=u["shop_id"]; session["role"]=u["role"]; session["name"]=u["name"]
            if u["role"]=="superadmin": return redirect("/superadmin")
            if u["role"]=="md": return redirect("/md")
            if u["role"]=="manager": return redirect("/manager")
            return redirect("/sales")
    opts=""
    for sh in shops:
        opts+="<option value='"+str(sh["id"])+"'>"+sh["name"]+"</option>"
    return top("Login","Select your Shop")+"<form method='post'><label>Shop</label><select name='shop_id' style='width:100%;padding:10px;margin:6px 0'>"+opts+"</select><label>PIN</label><input name='pin' type='password' placeholder='1234' style='width:100%;padding:10px;margin:6px 0'><button style='width:100%;padding:12px;background:#FF9800;border:none;border-radius:10px;font-weight:800'>Login</button></form><p>Demo PIN: 1234 for all</p>"+bottom()

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

@app.route("/superadmin", methods=["GET","POST"])
def superadmin():
    if session.get("role")!="superadmin": return redirect("/")
    c=db()
    if request.method=="POST" and request.form.get("action")=="add_shop":
        c.execute("INSERT INTO shops(name,sub_end,sub_paid,created) VALUES(?,?,?,?)",(request.form.get("name"),request.form.get("sub_end"),today_str(),today_str())); c.commit()
    if request.method=="POST" and request.form.get("action")=="toggle":
        sid=request.form.get("shop_id"); cur=c.execute("SELECT status FROM shops WHERE id=?",(sid,)).fetchone()["status"]
        new="off" if cur=="on" else "on"; c.execute("UPDATE shops SET status=? WHERE id=?",(new,sid)); c.commit()
    if request.method=="POST" and request.form.get("action")=="edit_sub":
        c.execute("UPDATE shops SET sub_end=? WHERE id=?",(request.form.get("sub_end"),request.form.get("shop_id"))); c.commit()
    if request.method=="POST" and request.form.get("action")=="edit_contact":
        c.execute("INSERT OR REPLACE INTO settings(id,shop_id,md_phone,mgr_phone,ceo_phone) VALUES((SELECT id FROM settings WHERE shop_id=?),?,?,?,?)",(request.form.get("shop_id"),request.form.get("shop_id"),request.form.get("md_phone"),request.form.get("mgr_phone"),request.form.get("ceo_phone"))); c.commit()
    shops=c.execute("SELECT * FROM shops").fetchall()
    users=c.execute("SELECT * FROM users").fetchall()
    traffic=c.execute("SELECT count(*) as n FROM traffic").fetchone()["n"]
    h=top("Superadmin Dashboard","Manage shops only - No performance / stock view per V11")
    h+="<div style='display:flex;gap:10px;flex-wrap:wrap'>"+card("Total Shops",len(shops))+card("Total Users",len(users))+card("Traffic / Usage",traffic)+"</div>"
    h+="<h3>Add Shop</h3><form method='post'><input type='hidden' name='action' value='add_shop'><input name='name' placeholder='Shop Name' required style='padding:10px;width:60%'><input type='date' name='sub_end' style='padding:10px'><button>Add Shop</button></form>"
    h+="<h3>Shops - Manage</h3>"
    for sh in shops:
        h+="<div style='background:#fff;padding:12px;border-radius:12px;margin:8px 0'><b>"+sh["name"]+"</b> - "+sh["status"]+" - Sub ends: "+str(sh["sub_end"] or "")+"<br>"
        h+="<form method='post' style='display:inline'><input type='hidden' name='action' value='toggle'><input type='hidden' name='shop_id' value='"+str(sh["id"])+"'><button>On/Off</button></form> "
        h+="<form method='post' style='display:inline'><input type='hidden' name='action' value='edit_sub'><input type='hidden' name='shop_id' value='"+str(sh["id"])+"'><input type='date' name='sub_end' value='"+str(sh["sub_end"] or "")+"'><button>Update Subscription</button></form>"
        h+="<form method='post' style='margin-top:6px'><input type='hidden' name='action' value='edit_contact'><input type='hidden' name='shop_id' value='"+str(sh["id"])+"'><input name='md_phone' placeholder='MD WhatsApp'><input name='mgr_phone' placeholder='Manager WhatsApp'><input name='ceo_phone' placeholder='CEO WhatsApp'><button>Save Contacts for Alerts</button></form>"
        h+="</div>"
    h+="<h3>Clients / Users</h3>"
    for u in users:
        h+="<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+u["name"]+" - "+u["role"]+" - Shop "+str(u["shop_id"])+" - "+str(u["phone"] or "")+"</div>"
    h+="<p style='color:#888'>Note: Superadmin does NOT view performance reports or stock/inventory for shops (removed in V11).</p><a href='/logout'>Logout</a>"
    return h+bottom()

# ===== V11 PART 2 - MD / MANAGER / SALES =====

def pie_html(title, data):
    # data = list of (label, value)
    total = sum([d[1] for d in data]) or 1
    h = "<div style='background:#fff;padding:12px;border-radius:12px;margin:10px 0'><h3>"+title+"</h3>"
    if not data:
        h += "<p>No data for this period</p></div>"; return h
    # simple bar pie alternative using colored bars - no external lib, no syntax risk
    colors = ["#FF9800","#4CAF50","#2196F3","#9C27B0","#F44336","#00BCD4","#FFC107"]
    for i,(lab,val) in enumerate(data):
        pct = round(val*100/total,1)
        col = colors[i % len(colors)]
        h += "<div style='margin:6px 0'><b>"+str(lab)+"</b> - N"+str(round(val,2))+" ("+str(pct)+"%)<div style='background:#eee;height:14px;border-radius:7px'><div style='width:"+str(pct)+"%;background:"+col+";height:14px;border-radius:7px'></div></div></div>"
    h += "<p>Total: N"+str(round(total,2))+"</p></div>"
    return h

@app.route("/md")
def md_page():
    if session.get("role") not in ["md","superadmin"]: return redirect("/")
    shop_id = session.get("shop") or 1
    c = db()
    s,e,label = parse_period()
    log_traffic(shop_id,"md")
    sales = c.execute("SELECT * FROM sales WHERE shop_id=? AND date BETWEEN ? AND ?",(shop_id,s,e)).fetchall()
    total_sales = sum([r["amount"] for r in sales]) or 0
    total_cost = sum([r["cost"] for r in sales]) or 0
    profit = total_sales - total_cost
    # sales by product for pie 1
    by_prod = {}
    for r in sales:
        by_prod[r["product"]] = by_prod.get(r["product"],0) + r["amount"]
    pie1_data = sorted(by_prod.items(), key=lambda x: x[1], reverse=True)[:7]
    # most selling by qty for pie 2
    by_qty = {}
    for r in sales:
        by_qty[r["product"]] = by_qty.get(r["product"],0) + (r["qty"] or 0)
    pie2_data = sorted(by_qty.items(), key=lambda x: x[1], reverse=True)[:7]
    # staff list without MD/CEO
    staff = c.execute("SELECT * FROM users WHERE shop_id=? AND role NOT IN ('md','superadmin')",(shop_id,)).fetchall()
    debtors = c.execute("SELECT * FROM debtors WHERE shop_id=? AND date BETWEEN ? AND ?",(shop_id,s,e)).fetchall()
    creditors = c.execute("SELECT * FROM creditors WHERE shop_id=?",(shop_id,)).fetchall()
    h = top("MD / CEO Dashboard","Performance - Period filter with Calendar")
    h += sub_alert(shop_id)
    h += period_bar()
    h += "<div style='display:flex;gap:10px;flex-wrap:wrap'>"+card("Sales (Period)",round(total_sales,2))+card("Cost",round(total_cost,2))+card("Profit",round(profit,2))+card("Debtors",len(debtors))+"</div>"
    h += pie_html("Pie Chart 1 - Sales by Amount and Percentage", pie1_data)
    h += pie_html("Pie Chart 2 - Most Selling Products (by Quantity)", pie2_data)
    h += "<h3>Staff List (MD/CEO removed from list)</h3>"
    for u in staff:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+u["name"]+" - "+u["role"]+" - "+str(u["phone"] or "")+"</div>"
    h += "<h3>Debtors in Period</h3>"
    for d in debtors:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+d["name"]+" - N"+str(d["amount"])+" - Due "+str(d["due_date"] or "")+" - "+str(d["reason"] or "")+"</div>"
    h += "<h3>Creditors / Settlement</h3>"
    for cr in creditors:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+cr["name"]+" - N"+str(cr["amount"])+" - Due "+str(cr["due_date"] or "")+" - "+str(cr["condition"] or "")+"</div>"
    h += "<br><a href='/manager'>Go to Manager</a> | <a href='/sales'>Go to Sales</a> | <a href='/logout'>Logout</a>"
    return h + bottom()

@app.route("/manager", methods=["GET","POST"])
def manager_page():
    if session.get("role") not in ["manager","md","superadmin"]: return redirect("/")
    shop_id = session.get("shop") or 1
    c = db()
    s,e,label = parse_period()
    log_traffic(shop_id,"manager")
    if request.method=="POST" and request.form.get("action")=="submit_day":
        opening=float(request.form.get("opening") or 0); closing=float(request.form.get("closing") or 0)
        sales_v=float(request.form.get("sales") or 0); purch=float(request.form.get("purchases") or 0)
        exp=float(request.form.get("expenditure") or 0); bad=float(request.form.get("bad_debt") or 0)
        debt_v=float(request.form.get("debtors_amt") or 0); cred_v=float(request.form.get("creditors_amt") or 0)
        profit_v = sales_v - exp - bad
        c.execute("INSERT INTO submissions(shop_id,user_id,date,opening,closing,sales,purchases,expenditure,profit,bad_debt,debtors_amt,creditors_amt,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(shop_id,session.get("uid"),today_str(),opening,closing,sales_v,purch,exp,profit_v,bad,debt_v,cred_v,request.form.get("note") or "")); c.commit()
        return redirect("/manager")
    if request.method=="POST" and request.form.get("action")=="add_creditor":
        c.execute("INSERT INTO creditors(shop_id,name,amount,condition,due_date,date) VALUES(?,?,?,?,?,?)",(shop_id,request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("condition"),request.form.get("due_date"),today_str())); c.commit()
        return redirect("/manager")
    if request.method=="POST" and request.form.get("action")=="add_request":
        c.execute("INSERT INTO requests(shop_id,user_id,type,title,amount,date) VALUES(?,?,?,?,?,?)",(shop_id,session.get("uid"),request.form.get("type"),request.form.get("title"),float(request.form.get("amount") or 0),today_str())); c.commit()
        return redirect("/manager")
    products = c.execute("SELECT * FROM products WHERE shop_id=?",(shop_id,)).fetchall()
    closing_stock_val = sum([(p["qty"] or 0)*(p["cost"] or 0) for p in products])
    closing_sell_val = sum([(p["qty"] or 0)*(p["price"] or 0) for p in products])
    sales_rows = c.execute("SELECT * FROM sales WHERE shop_id=? AND date BETWEEN ? AND ?",(shop_id,s,e)).fetchall()
    total_sales = sum([r["amount"] for r in sales_rows]) or 0
    subs = c.execute("SELECT * FROM submissions WHERE shop_id=? ORDER BY id DESC LIMIT 20",(shop_id,)).fetchall()
    creditors = c.execute("SELECT * FROM creditors WHERE shop_id=? ORDER BY due_date",(shop_id,)).fetchall()
    reqs = c.execute("SELECT * FROM requests WHERE shop_id=? ORDER BY id DESC LIMIT 20",(shop_id,)).fetchall()
    h = top("Manager Dashboard","Totals, Closing Stock, Settlement, Requests, Alerts")
    h += sub_alert(shop_id)
    h += period_bar()
    h += "<div style='display:flex;gap:10px;flex-wrap:wrap'>"+card("Sales (Period)",round(total_sales,2))+card("Closing Stock (Cost)",round(closing_stock_val,2))+card("Closing Stock (Selling)",round(closing_sell_val,2))+card("Creditors",len(creditors))+"</div>"
    h += "<h3>Alerts - Low Stock & Expiry</h3>"
    for p in products:
        if (p["qty"] or 0) <= (p["low_level"] or 5):
            h += "<div style='background:#FFCDD2;padding:8px;border-radius:8px;margin:4px 0'>LOW STOCK: "+p["name"]+" - Qty "+str(p["qty"])+"</div>"
        if p["expiry"]:
            try:
                days=(datetime.date.fromisoformat(p["expiry"])-datetime.date.today()).days
                if days<=30:
                    h += "<div style='background:#FFE0B2;padding:8px;border-radius:8px;margin:4px 0'>EXPIRY SOON: "+p["name"]+" - "+p["expiry"]+" ("+str(days)+" days)</div>"
            except: pass
    h += "<h3>Submit Daily Report - All 8 Fields</h3><form method='post'><input type='hidden' name='action' value='submit_day'>"
    h += "Opening <input name='opening' type='number' step='any' required style='width:100%;padding:8px'> Closing <input name='closing' type='number' step='any' required style='width:100%;padding:8px'> Sales <input name='sales' type='number' step='any' style='width:100%;padding:8px'> Purchases <input name='purchases' type='number' step='any' style='width:100%;padding:8px'> Expenditure <input name='expenditure' type='number' step='any' style='width:100%;padding:8px'> Bad Debt <input name='bad_debt' type='number' step='any' style='width:100%;padding:8px'> Debtors <input name='debtors_amt' type='number' step='any' style='width:100%;padding:8px'> Creditors <input name='creditors_amt' type='number' step='any' style='width:100%;padding:8px'> Note <input name='note' style='width:100%;padding:8px'><button style='width:100%;padding:10px;background:#FF9800;border:none;border-radius:10px;margin-top:6px'>Submit</button></form>"
    h += "<h3>Submitted History - Opening, Closing, Sales, Purchases, Expenditure, Profit/Loss, Bad Debt, Debtors & Creditors</h3>"
    for sb in subs:
        h += "<div style='background:#fff;padding:10px;border-radius:10px;margin:6px 0'><b>"+str(sb["date"])+"</b><br>Opening: "+str(sb["opening"])+" | Closing: "+str(sb["closing"])+" | Sales: "+str(sb["sales"])+" | Purchases: "+str(sb["purchases"])+"<br>Expenditure: "+str(sb["expenditure"])+" | Profit/Loss: "+str(sb["profit"])+" | Bad Debt: "+str(sb["bad_debt"])+"<br>Debtors: "+str(sb["debtors_amt"])+" | Creditors: "+str(sb["creditors_amt"])+"</div>"
    h += "<h3>Add Creditor + Settlement Timeline + Condition</h3><form method='post'><input type='hidden' name='action' value='add_creditor'><input name='name' placeholder='Creditor Name' required style='width:100%;padding:8px'> Amount <input name='amount' type='number' step='any' style='width:100%;padding:8px'> Condition <input name='condition' placeholder='e.g Pay in 14 days' style='width:100%;padding:8px'> Due Date <input type='date' name='due_date' style='width:100%;padding:8px'><button>Add Creditor</button></form>"
    for cr in creditors:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+cr["name"]+" - N"+str(cr["amount"])+" - Due "+str(cr["due_date"] or "")+" - "+str(cr["condition"] or "")+" - "+str(cr["status"])+"</div>"
    h += "<h3>Requests - Expenditure / Purchases Budget / Salary Schedule</h3><form method='post'><input type='hidden' name='action' value='add_request'><select name='type' style='width:100%;padding:8px'><option>Expenditure</option><option>Purchases Budget</option><option>Salary Schedule</option></select><input name='title' placeholder='Title' style='width:100%;padding:8px'> Amount <input name='amount' type='number' step='any' style='width:100%;padding:8px'><button>Submit Request</button></form>"
    for rq in reqs:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+rq["type"]+" - "+rq["title"]+" - N"+str(rq["amount"])+" - "+rq["status"]+"</div>"
    h += "<br><a href='/logout'>Logout</a>"
    return h + bottom()

@app.route("/sales", methods=["GET","POST"])
def sales_page():
    if session.get("role") not in ["sales","manager","md","superadmin"]: return redirect("/")
    shop_id = session.get("shop") or 1
    c = db()
    s,e,label = parse_period()
    log_traffic(shop_id,"sales")
    uid = session.get("uid")
    if request.method=="POST" and request.form.get("action")=="add_sale":
        prod = c.execute("SELECT * FROM products WHERE id=? AND shop_id=?",(request.form.get("product_id"),shop_id)).fetchone()
        if prod:
            qty=float(request.form.get("qty") or 0); amt=qty*(prod["price"] or 0); cost=qty*(prod["cost"] or 0)
            c.execute("INSERT INTO sales(shop_id,user_id,product,qty,amount,cost,date,created) VALUES(?,?,?,?,?,?,?,?)",(shop_id,uid,prod["name"],qty,amt,cost,today_str(),today_str()))
            c.execute("UPDATE products SET qty=qty-? WHERE id=?",(qty,prod["id"])); c.commit()
        return redirect("/sales")
    if request.method=="POST" and request.form.get("action")=="add_debtor":
        c.execute("INSERT INTO debtors(shop_id,user_id,name,amount,reason,due_date,date) VALUES(?,?,?,?,?,?,?)",(shop_id,uid,request.form.get("name"),float(request.form.get("amount") or 0),request.form.get("reason"),request.form.get("due_date"),today_str())); c.commit()
        return redirect("/sales")
    products = c.execute("SELECT * FROM products WHERE shop_id=?",(shop_id,)).fetchall()
    my_sales = c.execute("SELECT * FROM sales WHERE shop_id=? AND user_id=? AND date BETWEEN ? AND ? ORDER BY id DESC",(shop_id,uid,s,e)).fetchall()
    my_debtors = c.execute("SELECT * FROM debtors WHERE shop_id=? AND user_id=? AND date BETWEEN ? AND ? ORDER BY id DESC",(shop_id,uid,s,e)).fetchall()
    total_my = sum([r["amount"] for r in my_sales]) or 0
    total_debt = sum([r["amount"] for r in my_debtors]) or 0
    h = top("Salesperson Dashboard","Sell, Debtors, Breakdown by Calendar - No Stock Report in V11")
    h += sub_alert(shop_id)
    h += period_bar()
    h += "<div style='display:flex;gap:10px;flex-wrap:wrap'>"+card("My Sales (Period)",round(total_my,2))+card("My Debtors (Period)",round(total_debt,2))+card("Sales Count",len(my_sales))+"</div>"
    h += "<h3>Inventory - For Selling Only (Cost & Selling Prices)</h3>"
    for p in products:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+p["name"]+" - Qty "+str(p["qty"])+" - Cost N"+str(p["cost"])+" - Selling N"+str(p["price"])+"</div>"
    h += "<h3>Add Sales - Sell</h3><form method='post'><input type='hidden' name='action' value='add_sale'><select name='product_id' style='width:100%;padding:8px'>"
    for p in products:
        h += "<option value='"+str(p["id"])+"'>"+p["name"]+" - N"+str(p["price"])+"</option>"
    h += "</select> Qty <input name='qty' type='number' step='any' required style='width:100%;padding:8px'><button style='width:100%;padding:10px;background:#4CAF50;color:#fff;border:none;border-radius:10px'>Add Sale</button></form>"
    h += "<h3>Add Debtor - With Settlement Timeline + Reason</h3><form method='post'><input type='hidden' name='action' value='add_debtor'><input name='name' placeholder='Debtor Name' required style='width:100%;padding:8px'> Amount <input name='amount' type='number' step='any' style='width:100%;padding:8px'> Reason <input name='reason' placeholder='Reason for Debtor' style='width:100%;padding:8px'> Due Date <input type='date' name='due_date' style='width:100%;padding:8px'><button>Add Debtor</button></form>"
    h += "<h3>Breakdown - My Sales / Debtors Reports (Use Calendar Above for Any Period)</h3><h4>Sales Breakdown</h4>"
    for r in my_sales:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+str(r["date"])+" - "+r["product"]+" x "+str(r["qty"])+" = N"+str(r["amount"])+"</div>"
    h += "<h4>Debtors Breakdown</h4>"
    for d in my_debtors:
        h += "<div style='background:#fff;padding:8px;border-radius:8px;margin:4px 0'>"+str(d["date"])+" - "+d["name"]+" - N"+str(d["amount"])+" - Due "+str(d["due_date"] or "")+" - Reason: "+str(d["reason"] or "")+"</div>"
    h += "<p style='color:#888'>Note: Stock/Inventory Report removed. My Sales Reports merged into Breakdown above.</p><br><a href='/logout'>Logout</a>"
    return h + bottom()

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000)); app.run(host="0.0.0.0",port=port)

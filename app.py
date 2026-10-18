import os, secrets, sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
ROOT = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
# Vercel's deployed filesystem is read-only except /tmp. SQLite there is only a
# temporary fallback for preview; use DATABASE_URL for persistent production data.
LOCAL_DB = (Path("/tmp") / "elian_store_preview.db") if os.getenv("VERCEL") else (ROOT / "instance" / "elian_store.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "0") == "1"

PRODUCTS = [
    ("Script Auto Order", "Produk digital"),
    ("Claude Max", "Langganan digital"),
    ("ChatGPT Plus", "Langganan digital"),
    ("Upgrade Premium E-Wallet", "Layanan upgrade"),
    ("Alight Motion Premium", "Langganan digital"),
]

class DB:
    """Small adapter so the same queries work with local SQLite and hosted PostgreSQL."""
    def __init__(self):
        self.pg = IS_POSTGRES
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
        else:
            LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(LOCAL_DB)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql, params=()):
        if self.pg:
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def db():
    if "db" not in g:
        g.db = DB()
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()

def init_db():
    with app.app_context():
        conn = db()
        if IS_POSTGRES:
            statements = [
                """CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Produk digital',
                    description TEXT NOT NULL DEFAULT 'Deskripsi akan dilengkapi oleh owner.',
                    price BIGINT NOT NULL DEFAULT 1 CHECK(price >= 0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY, access_code_hash TEXT NOT NULL, customer_name TEXT NOT NULL,
                    customer_contact TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
                    product_name TEXT NOT NULL, amount BIGINT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS owner_credentials (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL, password_hash TEXT NOT NULL)"""
            ]
            for s in statements: conn.execute(s)
            pcount = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
            if pcount == 0:
                now = datetime.now(timezone.utc).isoformat()
                for name, category in PRODUCTS:
                    conn.execute("INSERT INTO products(name,category,description,price,stock,active,created_at) VALUES(?,?,?,?,?,?,?)",
                                 (name, category, "Deskripsi dan ketentuan produk perlu dilengkapi owner.", 1, 0, 1, now))
        else:
            conn.execute("""CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Produk digital',
                description TEXT NOT NULL DEFAULT 'Deskripsi akan dilengkapi oleh owner.',
                price INTEGER NOT NULL DEFAULT 1 CHECK(price >= 0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY, access_code_hash TEXT NOT NULL, customer_name TEXT NOT NULL,
                customer_contact TEXT NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL,
                amount INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS owner_credentials (
                id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL)""")
            pcount = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
            if pcount == 0:
                now = datetime.now(timezone.utc).isoformat()
                for name, category in PRODUCTS:
                    conn.execute("INSERT INTO products(name,category,description,price,stock,active,created_at) VALUES(?,?,?,?,?,?,?)",
                                 (name, category, "Deskripsi dan ketentuan produk perlu dilengkapi owner.", 1, 0, 1, now))
        owner = conn.execute("SELECT id FROM owner_credentials WHERE id=1").fetchone()
        if not owner:
            conn.execute("INSERT INTO owner_credentials(id,username,password_hash) VALUES(1,?,?)",
                         (os.getenv("OWNER_USERNAME", "owner223"), generate_password_hash(os.getenv("OWNER_PASSWORD", "owner224"))))
        conn.commit()

def owner_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("owner_logged_in"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def telegram(message, channel=False):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target = os.getenv("TELEGRAM_CHANNEL_CHAT_ID" if channel else "TELEGRAM_OWNER_CHAT_ID", "").strip()
    if not token or not target:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": target, "text": message, "disable_web_page_preview": True}, timeout=8)
        return r.ok and r.json().get("ok", False)
    except Exception:
        app.logger.exception("Telegram notification failed")
        return False

@app.template_filter("idr")
def idr(value):
    return "Rp" + f"{int(value):,}".replace(",", ".")

@app.route("/")
def home():
    products = db().execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()
    return render_template("index.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db().execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
    if not product: abort(404)
    return render_template("product.html", product=product)

@app.route("/checkout/<int:product_id>", methods=["GET", "POST"])
def checkout(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
    if not product: abort(404)
    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        contact = request.form.get("customer_contact", "").strip()
        if not name or not contact or len(name) > 100 or len(contact) > 160:
            flash("Isi nama dan kontak yang valid.", "error")
            return render_template("checkout.html", product=product)
        order_id, access_code = "EL-" + secrets.token_hex(5).upper(), secrets.token_urlsafe(12)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=60)
        conn.execute("""INSERT INTO orders(id,access_code_hash,customer_name,customer_contact,product_id,product_name,amount,status,created_at,expires_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (order_id, generate_password_hash(access_code), name, contact, product["id"], product["name"],
                      product["price"], "Menunggu pembayaran", now.isoformat(), expires.isoformat()))
        conn.commit()
        telegram(f"Pesanan baru: {order_id}\nProduk: {product['name']}\nNominal: {idr(product['price'])}\nStatus: Menunggu pembayaran")
        return render_template("order_created.html", order_id=order_id, access_code=access_code, product=product,
                               expires=expires.strftime("%Y-%m-%d %H:%M UTC"))
    return render_template("checkout.html", product=product)

@app.route("/track", methods=["GET", "POST"])
def track():
    order, error = None, None
    if request.method == "POST":
        oid, code = request.form.get("order_id", "").strip().upper(), request.form.get("access_code", "").strip()
        row = db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if row and check_password_hash(row["access_code_hash"], code): order = row
        else: error = "Pesanan tidak ditemukan atau kode akses salah."
    return render_template("track.html", order=order, error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = request.form.get("username", ""), request.form.get("password", "")
        owner = db().execute("SELECT * FROM owner_credentials WHERE id=1").fetchone()
        if owner and secrets.compare_digest(username, owner["username"]) and check_password_hash(owner["password_hash"], password):
            session.clear()
            session["owner_logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/owner")
@owner_required
def dashboard():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    orders = conn.execute("SELECT id,customer_name,product_name,amount,status,created_at FROM orders ORDER BY created_at DESC LIMIT 50").fetchall()
    stats = {"products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
             "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
             "pending": conn.execute("SELECT COUNT(*) FROM orders WHERE status='Menunggu pembayaran'").fetchone()[0]}
    return render_template("dashboard.html", products=products, orders=orders, stats=stats)

@app.route("/owner/product/<int:product_id>", methods=["POST"])
@owner_required
def update_product(product_id):
    name = request.form.get("name", "").strip()
    try:
        price, stock = int(request.form.get("price", "")), int(request.form.get("stock", ""))
        if not name or price < 0 or stock < 0: raise ValueError()
    except ValueError:
        flash("Nama, harga, atau stok tidak valid.", "error")
        return redirect(url_for("dashboard"))
    conn = db()
    conn.execute("UPDATE products SET name=?,price=?,stock=?,active=? WHERE id=?",
                 (name, price, stock, 1 if request.form.get("active") == "on" else 0, product_id))
    conn.commit()
    flash("Produk diperbarui.", "success")
    return redirect(url_for("dashboard"))

@app.route("/health")
def health():
    return {"status": "ok", "database": "postgres" if IS_POSTGRES else "local-sqlite", "payment_gateway": "not_configured"}

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", title="Halaman tidak ditemukan", message="Halaman yang kamu cari tidak tersedia."), 404

init_db()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

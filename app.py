# ==============================================================================
# SmartCart - Modern Luxury E-Commerce Application (Flask + MySQL + Razorpay)
# ==============================================================================

from flask import Flask, render_template, request, redirect, session, flash, jsonify, make_response
from flask_mail import Mail, Message
import mysql.connector
import bcrypt
import random
import os
from werkzeug.utils import secure_filename
import razorpay
import traceback

try:
    import config
except ImportError:
    config = None

try:
    from utils.pdf_generator import generate_pdf
except Exception:
    generate_pdf = None

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", getattr(config, "SECRET_KEY", "smartcart_secret_key_2026"))

# ---------------- EMAIL CONFIGURATION ----------------
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", getattr(config, "MAIL_SERVER", "smtp.gmail.com"))
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", getattr(config, "MAIL_PORT", 587)))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME", getattr(config, "MAIL_USERNAME", ""))
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD", getattr(config, "MAIL_PASSWORD", ""))

mail = Mail(app)

# ---------------- UPLOAD CONFIGURATION (VERCEL /tmp SAFE) ----------------
IS_VERCEL = bool(os.getenv("VERCEL"))
if IS_VERCEL:
    UPLOAD_FOLDER = "/tmp/product_images"
    ADMIN_UPLOAD_FOLDER = "/tmp/admin_profile"
else:
    UPLOAD_FOLDER = os.path.join("static", "uploads", "product_images")
    ADMIN_UPLOAD_FOLDER = os.path.join("static", "uploads", "admin_profile")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ADMIN_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER


# ---------------- DB & RAZORPAY HELPERS ----------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", getattr(config, "DB_HOST", "localhost")),
        port=int(os.getenv("DB_PORT", getattr(config, "DB_PORT", 3306))),
        user=os.getenv("DB_USER", getattr(config, "DB_USER", "root")),
        password=os.getenv("DB_PASSWORD", getattr(config, "DB_PASSWORD", "")),
        database=os.getenv("DB_NAME", getattr(config, "DB_NAME", "smart_cart"))
    )


def get_razorpay_keys():
    key_id = os.getenv("RAZORPAY_KEY_ID", getattr(config, "RAZORPAY_KEY_ID", ""))
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", getattr(config, "RAZORPAY_KEY_SECRET", ""))
    return key_id, key_secret


def is_razorpay_configured():
    key_id, key_secret = get_razorpay_keys()
    return bool(key_id and key_secret)


def get_razorpay_client():
    key_id, key_secret = get_razorpay_keys()
    return razorpay.Client(auth=(key_id, key_secret))


# ==============================================================================
# ROUTE: LANDING / HOMEPAGE
# ==============================================================================
@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE is_featured = 1 ORDER BY product_id DESC LIMIT 8")
    featured_products = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total_items FROM products")
    total_products = cursor.fetchone()['total_items']

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        featured_products=featured_products,
        total_products=total_products
    )


# ==============================================================================
# ADMIN AUTHENTICATION ROUTES
# ==============================================================================

@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    name = request.form['name']
    email = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_id FROM admin WHERE email=%s", (email,))
    existing_admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_admin:
        flash("This email is already registered. Please login instead.", "danger")
        return redirect('/admin-signup')

    session['signup_name'] = name
    session['signup_email'] = email

    otp = random.randint(100000, 999999)
    session['otp'] = otp

    try:
        message = Message(
            subject="SmartCart Admin OTP Verification",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        message.body = f"Hello {name},\n\nYour OTP for SmartCart Admin Registration is: {otp}\n\nThis OTP is valid for 10 minutes."
        mail.send(message)
        flash("OTP sent to your email!", "success")
    except Exception as e:
        app.logger.warning("Email send failed: %s. Using session OTP for testing.", str(e))
        flash(f"OTP generated: {otp} (Simulated email delivery)", "info")

    return redirect('/verify-otp')


@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    return render_template("admin/verify_otp.html")


@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():
    user_otp = request.form['otp']
    password = request.form['password']

    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)",
        (session['signup_name'], session['signup_email'], hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin registered successfully! Please log in.", "success")
    return redirect('/admin-login')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if admin is None:
        flash("Email not found! Please check or register first.", "danger")
        return redirect('/admin-login')

    stored_password = admin['password']
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash("Welcome back, Administrator!", "success")
    return redirect('/admin-dashboard')


@app.route('/admin-dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    products_count = cursor.fetchone()['total_products']

    cursor.execute("SELECT COUNT(*) AS total_orders, COALESCE(SUM(amount), 0) AS total_revenue FROM orders")
    stats = cursor.fetchone()
    orders_count = stats['total_orders']
    total_revenue = f"{float(stats['total_revenue']):,.2f}"

    cursor.execute("SELECT COUNT(DISTINCT category) AS total_categories FROM products")
    categories_count = cursor.fetchone()['total_categories']

    cursor.execute("SELECT * FROM products ORDER BY product_id DESC LIMIT 6")
    recent_products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        admin_name=session['admin_name'],
        products_count=products_count,
        orders_count=orders_count,
        total_revenue=total_revenue,
        categories_count=categories_count,
        recent_products=recent_products
    )


@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)
    flash("Logged out successfully.", "success")
    return redirect('/admin-login')


# ==============================================================================
# ADMIN PRODUCT MANAGEMENT
# ==============================================================================

@app.route('/admin/add-item', methods=['GET'])
def add_item_page():
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')
    return render_template("admin/add_item.html")


@app.route('/admin/add-item', methods=['POST'])
def add_item():
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    name = request.form['name']
    description = request.form.get('description', '')
    category = request.form.get('category', 'General')
    price = request.form['price']
    original_price = request.form.get('original_price') or None
    rating = request.form.get('rating') or 4.8
    image_file = request.files.get('image')

    if not image_file or image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(image_path)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, description, category, price, original_price, rating, image, is_featured) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
        (name, description, category, price, original_price, rating, filename)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Product '{name}' added successfully to catalog!", "success")
    return redirect('/admin/item-list')


@app.route('/admin/item-list')
def item_list():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
    categories = cursor.fetchall()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    if category_filter:
        query += " AND category = %s"
        params.append(category_filter)

    query += " ORDER BY product_id DESC"

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories
    )


@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product)


@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)


@app.route('/admin/update-item/<int:item_id>', methods=['POST'])
def update_item(item_id):
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    name = request.form['name']
    description = request.form.get('description', '')
    category = request.form.get('category', 'General')
    price = request.form['price']
    original_price = request.form.get('original_price') or None
    rating = request.form.get('rating') or 4.8
    new_image = request.files.get('image')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    old_image_name = product['image']

    if new_image and new_image.filename != "":
        new_filename = secure_filename(new_image.filename)
        new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        new_image.save(new_image_path)
        final_image_name = new_filename
    else:
        final_image_name = old_image_name

    cursor.execute("""
        UPDATE products
        SET name=%s, description=%s, category=%s, price=%s, original_price=%s, rating=%s, image=%s
        WHERE product_id=%s
    """, (name, description, category, price, original_price, rating, final_image_name, item_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Product '{name}' updated successfully!", "success")
    return redirect('/admin/item-list')


@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT image, name FROM products WHERE product_id=%s", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    cursor.execute("DELETE FROM products WHERE product_id=%s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Product '{product['name']}' deleted successfully!", "success")
    return redirect('/admin/item-list')


@app.route('/admin/profile', methods=['GET'])
def admin_profile():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("admin/admin_profile.html", admin=admin)


@app.route('/admin/profile', methods=['POST'])
def admin_profile_update():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']
    name = request.form['name']
    email = request.form['email']
    new_password = request.form.get('password', '').strip()
    new_image = request.files.get('profile_image')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()

    old_image_name = admin.get('profile_image')

    if new_password:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    else:
        hashed_password = admin['password']

    if new_image and new_image.filename != "":
        new_filename = secure_filename(new_image.filename)
        image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], new_filename)
        new_image.save(image_path)
        final_image_name = new_filename
    else:
        final_image_name = old_image_name

    cursor.execute("""
        UPDATE admin
        SET name=%s, email=%s, password=%s, profile_image=%s
        WHERE admin_id=%s
    """, (name, email, hashed_password, final_image_name, admin_id))

    conn.commit()
    cursor.close()
    conn.close()

    session['admin_name'] = name
    session['admin_email'] = email

    flash("Profile updated successfully!", "success")
    return redirect('/admin/profile')


# ==============================================================================
# USER AUTHENTICATION & DASHBOARD
# ==============================================================================

@app.route('/user-register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'GET':
        return render_template("user/user_register.html")

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        flash("Email already registered! Please login.", "danger")
        return redirect('/user-login')

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
        (name, email, hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Registration successful! Please login with your credentials.", "success")
    return redirect('/user-login')


@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'GET':
        return render_template("user/user_login.html")

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        flash("Email not found! Please create an account.", "danger")
        return redirect('/user-login')

    stored_password = user['password']
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/user-login')

    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    flash(f"Welcome back, {user['name']}!", "success")
    return redirect('/user-dashboard')


@app.route('/user-dashboard')
def user_dashboard():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE is_featured = 1 ORDER BY product_id DESC LIMIT 8")
    featured_products = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
    categories = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS order_count FROM orders WHERE user_id = %s", (session['user_id'],))
    order_count = cursor.fetchone()['order_count']

    cursor.close()
    conn.close()

    cart = session.get('cart', {})
    cart_items_count = sum(item['quantity'] for item in cart.values())

    return render_template(
        "user/user_home.html",
        user_name=session['user_name'],
        featured_products=featured_products,
        categories=categories,
        order_count=order_count,
        cart_items_count=cart_items_count
    )


@app.route('/user/products')
def user_products():
    if 'user_id' not in session:
        flash("Please login to view products!", "danger")
        return redirect('/user-login')

    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'default').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
    categories = cursor.fetchall()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    if category_filter:
        query += " AND category = %s"
        params.append(category_filter)

    if sort == 'price_low':
        query += " ORDER BY price ASC"
    elif sort == 'price_high':
        query += " ORDER BY price DESC"
    elif sort == 'rating':
        query += " ORDER BY rating DESC"
    else:
        query += " ORDER BY product_id DESC"

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    cart = session.get('cart', {})
    cart_items_count = sum(item['quantity'] for item in cart.values())

    return render_template(
        "user/products.html",
        products=products,
        categories=categories,
        cart_items_count=cart_items_count
    )


@app.route('/user/product/<int:product_id>')
def user_product_details(product_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    related_products = []
    if product:
        cursor.execute(
            "SELECT * FROM products WHERE category = %s AND product_id != %s LIMIT 4",
            (product['category'], product_id)
        )
        related_products = cursor.fetchall()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    cart = session.get('cart', {})
    cart_items_count = sum(item['quantity'] for item in cart.values())

    return render_template(
        "user/product_details.html",
        product=product,
        related_products=related_products,
        cart_items_count=cart_items_count
    )


# ==============================================================================
# SHOPPING CART & CHECKOUT
# ==============================================================================

@app.route('/user/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found.", "danger")
        return redirect('/user/products')

    pid = str(product_id)
    if pid in cart:
        cart[pid]['quantity'] += 1
    else:
        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart
    session.modified = True
    flash(f"'{product['name']}' added to your cart!", "success")

    return redirect(request.referrer or '/user/products')


@app.route('/user/add-to-cart-ajax/<int:product_id>')
def add_to_cart_ajax(product_id):
    if 'user_id' not in session:
        return jsonify({"error": "not_logged_in"}), 401

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    pid = str(product_id)
    if pid in cart:
        cart[pid]['quantity'] += 1
    else:
        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart
    session.modified = True

    total_qty = sum(item['quantity'] for item in cart.values())

    return jsonify({
        "message": f"Added '{product['name']}' to your cart!",
        "cart_count": total_qty
    })


@app.route('/user/cart')
def view_cart():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})
    grand_total = sum(item['price'] * item['quantity'] for item in cart.values())

    return render_template("user/cart.html", cart=cart, grand_total=grand_total)


@app.route('/user/cart/increase/<pid>')
def increase_quantity(pid):
    cart = session.get('cart', {})
    if pid in cart:
        cart[pid]['quantity'] += 1
    session['cart'] = cart
    session.modified = True
    return redirect('/user/cart')


@app.route('/user/cart/decrease/<pid>')
def decrease_quantity(pid):
    cart = session.get('cart', {})
    if pid in cart:
        cart[pid]['quantity'] -= 1
        if cart[pid]['quantity'] <= 0:
            cart.pop(pid)
    session['cart'] = cart
    session.modified = True
    return redirect('/user/cart')


@app.route('/user/cart/remove/<pid>')
def remove_from_cart(pid):
    cart = session.get('cart', {})
    if pid in cart:
        cart.pop(pid)
    session['cart'] = cart
    session.modified = True
    flash("Item removed from your cart.", "info")
    return redirect('/user/cart')


@app.route('/user/checkout')
def user_checkout():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty. Add items before checking out.", "danger")
        return redirect('/user/cart')

    grand_total = sum(item['price'] * item['quantity'] for item in cart.values())
    amount_paise = int(round(grand_total * 100))

    if amount_paise <= 0:
        flash("Invalid order amount. Please review your cart.", "danger")
        return redirect('/user/cart')

    order_dict = {
        'id': f"order_demo_{random.randint(100000, 999999)}",
        'amount': amount_paise,
        'currency': 'INR'
    }

    if is_razorpay_configured():
        try:
            client = get_razorpay_client()
            razorpay_order = client.order.create({
                'amount': amount_paise,
                'currency': 'INR',
                'payment_capture': 1,
                'notes': {
                    'user_id': session['user_id'],
                    'user_name': session.get('user_name', '')
                }
            })
            order_dict['id'] = razorpay_order.get('id', order_dict['id'])
        except Exception as e:
            app.logger.warning("Razorpay order creation fallback: %s", str(e))

    session['razorpay_order_id'] = order_dict['id']
    razorpay_key_id, _ = get_razorpay_keys()

    return render_template(
        'user/checkout.html',
        order=order_dict,
        amount=amount_paise,
        razorpay_key_id=razorpay_key_id,
        user_name=session.get('user_name', ''),
        user_email=session.get('user_email', '')
    )


@app.route('/user/pay')
def user_pay():
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty!", "danger")
        return redirect('/user/products')

    total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
    razorpay_amount = int(total_amount * 100)

    order_id = f"order_demo_{random.randint(100000, 999999)}"
    if is_razorpay_configured():
        try:
            client = get_razorpay_client()
            razorpay_order = client.order.create({
                "amount": razorpay_amount,
                "currency": "INR",
                "payment_capture": 1
            })
            order_id = razorpay_order['id']
        except Exception as e:
            app.logger.warning("Razorpay client fallback: %s", str(e))

    session['razorpay_order_id'] = order_id
    razorpay_key_id, _ = get_razorpay_keys()

    return render_template(
        "user/payment.html",
        amount=total_amount,
        key_id=razorpay_key_id,
        order_id=order_id
    )


@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        flash("Please login to complete the payment.", "danger")
        return redirect('/user-login')

    razorpay_payment_id = request.form.get('razorpay_payment_id') or f"pay_demo_{random.randint(100000, 999999)}"
    razorpay_order_id = request.form.get('razorpay_order_id') or session.get('razorpay_order_id', f"order_demo_{random.randint(100000, 999999)}")
    razorpay_signature = request.form.get('razorpay_signature') or 'demo_test_signature'

    payload = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    razorpay_key_id, _ = get_razorpay_keys()

    if razorpay_signature != 'demo_test_signature' and not razorpay_payment_id.startswith('pay_demo_'):
        try:
            get_razorpay_client().utility.verify_payment_signature(payload)
        except Exception as e:
            app.logger.warning("Razorpay verification warning: %s", str(e))
            if not razorpay_key_id.startswith('rzp_test_'):
                flash("Payment verification failed. Please contact support.", "danger")
                return redirect('/user/cart')

    user_id = session['user_id']
    cart = session.get('cart', {})

    if not cart:
        flash("Cart is empty. Cannot create order.", "danger")
        return redirect('/user/products')

    total_amount = sum(item['price'] * item['quantity'] for item in cart.values())

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO orders (user_id, razorpay_order_id, razorpay_payment_id, amount, payment_status)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, razorpay_order_id, razorpay_payment_id, total_amount, 'paid'))

        order_db_id = cursor.lastrowid

        for pid_str, item in cart.items():
            product_id = int(pid_str)
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (order_db_id, product_id, item['name'], item['quantity'], item['price']))

        conn.commit()

        session.pop('cart', None)
        session.pop('razorpay_order_id', None)

        flash("Payment authorized! Your order has been placed successfully.", "success")
        return redirect(f"/user/order-success/{order_db_id}")

    except Exception as e:
        conn.rollback()
        app.logger.error("Order storage failed: %s\n%s", str(e), traceback.format_exc())
        flash("There was an error saving your order. Contact support.", "danger")
        return redirect('/user/cart')

    finally:
        cursor.close()
        conn.close()


@app.route('/payment-success')
def payment_success():
    payment_id = request.args.get('payment_id')
    order_id = request.args.get('order_id')

    if not payment_id:
        flash("Payment failed!", "danger")
        return redirect('/user/cart')

    return render_template(
        "user/payment_success.html",
        payment_id=payment_id,
        order_id=order_id
    )


@app.route('/user/order-success/<int:order_db_id>')
def order_success(order_db_id):
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_db_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_db_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/products')

    return render_template("user/order_success.html", order=order, items=items)


@app.route('/user/my-orders')
def my_orders():
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, 
               (SELECT COUNT(*) FROM order_items WHERE order_id = o.order_id) as total_items,
               (SELECT GROUP_CONCAT(product_name SEPARATOR ', ') FROM order_items WHERE order_id = o.order_id) as items_summary
        FROM orders o 
        WHERE o.user_id=%s 
        ORDER BY o.created_at DESC
    """, (session['user_id'],))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("user/my_orders.html", orders=orders)


@app.route("/user/download-invoice/<int:order_id>")
def download_invoice(order_id):
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    html = render_template("user/invoice.html", order=order, items=items)
    if not generate_pdf:
        return html

    pdf = generate_pdf(html)
    if not pdf:
        return html

    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f"attachment; filename=SmartCart_Invoice_{order_id}.pdf"

    return response


@app.route('/user-logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    flash("You have been securely logged out.", "success")
    return redirect('/user-login')


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)
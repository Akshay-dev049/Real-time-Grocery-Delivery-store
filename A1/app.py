from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import razorpay, random, math, re, requests
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "grocery_secret_2025"

# ── DATABASE CONFIG ──────────────────────────────────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///grocery.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── RAZORPAY ─────────────────────────────────────────────────────────────────
razorpay_key_id     = "rzp_test_SV6BgViXri03IR"
razorpay_key_secret = "D1jRh6P2YfrLDyMlDrSXh8el"
client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

# ── DELIVERY CONFIG ───────────────────────────────────────────────────────────
DELIVERY_RADIUS_KM = 30


# ════════════════════════════════════════════════════════════════════════════
#  MODELS
# ════════════════════════════════════════════════════════════════════════════

class User(db.Model):
    __tablename__ = 'users'
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(100))
    email             = db.Column(db.String(100), unique=True)
    password          = db.Column(db.String(255))
    role              = db.Column(db.String(20), default='user')
    latitude          = db.Column(db.Float)
    longitude         = db.Column(db.Float)
    phone             = db.Column(db.String(20))
    security_question = db.Column(db.String(255))
    security_answer   = db.Column(db.String(255))


class Product(db.Model):
    __tablename__ = 'products'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100))
    price    = db.Column(db.Float)
    category = db.Column(db.String(50))
    image    = db.Column(db.String(255))
    stock    = db.Column(db.Integer, default=100)


class Cart(db.Model):
    __tablename__ = 'cart'
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True)


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id         = db.Column(db.Integer, primary_key=True)
    cart_id    = db.Column(db.Integer, db.ForeignKey('cart.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity   = db.Column(db.Integer, default=1)


class Order(db.Model):
    __tablename__ = 'orders'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'))
    total_price  = db.Column(db.Float)
    status       = db.Column(db.String(50), default='Pending')
    payment_id   = db.Column(db.String(100))
    address      = db.Column(db.Text)
    phone        = db.Column(db.String(20))
    user_lat     = db.Column(db.Float)
    user_lng     = db.Column(db.Float)
    delivery_lat = db.Column(db.Float)
    delivery_lng = db.Column(db.Float)
    created_at   = db.Column(db.DateTime, server_default=db.func.now())


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity   = db.Column(db.Integer)
    price      = db.Column(db.Float)


class Settings(db.Model):
    __tablename__ = 'settings'
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True)
    value = db.Column(db.Text)


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    rl = lambda d: d * math.pi / 180
    dlat = rl(lat2 - lat1)
    dlng = rl(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(rl(lat1)) * math.cos(rl(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_setting(key, default=None):
    s = Settings.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value):
    s = Settings.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(Settings(key=key, value=value))
    db.session.commit()


def get_store():
    class StoreInfo:
        store_name = get_setting('store_name', 'FreshGrocery Store')
        address    = get_setting('store_address', 'Address not set by admin')
        lat        = float(get_setting('store_lat', 0) or 0)
        lng        = float(get_setting('store_lng', 0) or 0)
        radius_km  = float(get_setting('store_radius_km', 30) or 30)
    return StoreInfo()


# ════════════════════════════════════════════════════════════════════════════
#  CONTEXT PROCESSOR
# ════════════════════════════════════════════════════════════════════════════

@app.context_processor
def inject_user():
    user = None
    if session.get('user_id'):
        user = User.query.get(session['user_id'])
    return dict(user=user)


# ════════════════════════════════════════════════════════════════════════════
#  HOME & SEARCH
# ════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    products  = Product.query.all()
    has_order = False
    if session.get('user_id'):
        has_order = bool(Order.query.filter_by(user_id=session['user_id']).first())
    return render_template('home.html', products=products, has_order=has_order)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if q:
        products = Product.query.filter(
            db.or_(
                Product.name.ilike(f'%{q}%'),
                Product.category.ilike(f'%{q}%')
            )
        ).all()
    else:
        products = Product.query.all()
    has_order = False
    if session.get('user_id'):
        has_order = bool(Order.query.filter_by(user_id=session['user_id']).first())
    return render_template('home.html', products=products, has_order=has_order, search_query=q)


# ════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name  = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        security_question = request.form.get('security_question', '').strip()
        security_answer   = request.form.get('security_answer', '').strip().lower()

        # Validations
        if not name or not email or not password:
            return render_template('register.html', error='Please fill in all required fields.')

        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered! Please login.')

        if not security_question or not security_answer:
            return render_template('register.html',
                                   error='Please select a security question and provide an answer.')

        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters.')

        user = User(
            name              = name,
            email             = email,
            password          = generate_password_hash(password),
            phone             = phone,
            security_question = security_question,
            security_answer   = security_answer
        )
        db.session.add(user)
        db.session.commit()
        return render_template('register.html',
                               success='Account created successfully! Please login.')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role']    = user.role
            if user.role == 'admin':
                return redirect('/admin')
            elif user.role == 'delivery':
                return redirect('/delivery')
            else:
                return redirect('/')
        return render_template('login.html', error='Invalid email or password.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD  (3-step: email → security question → reset)
# ════════════════════════════════════════════════════════════════════════════

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Step 1 – show email form (GET) or validate email and advance to Step 2 (POST).
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            return render_template('forgot_password.html', step='email',
                                   error='Please enter your email address.')

        user = User.query.filter_by(email=email).first()

        if not user:
            return render_template('forgot_password.html', step='email',
                                   error='No account found with that email address.')

        if not user.security_question or not user.security_answer:
            return render_template('forgot_password.html', step='email',
                                   error='This account has no security question set. Please contact support.')

        # Save email in session so verify-answer route can use it
        session['reset_email'] = user.email

        return render_template('forgot_password.html',
                               step='question',
                               question=user.security_question)

    # GET – always show Step 1
    return render_template('forgot_password.html', step='email')


@app.route('/verify-answer', methods=['POST'])
def verify_answer():
    """
    Step 2 – validate security answer and advance to Step 3.
    """
    email = session.get('reset_email')
    if not email:
        # Session expired or direct access – send back to Step 1
        return redirect('/forgot-password')

    user = User.query.filter_by(email=email).first()
    if not user:
        session.pop('reset_email', None)
        return redirect('/forgot-password')

    answer = request.form.get('answer', '').strip().lower()

    if not answer:
        return render_template('forgot_password.html',
                               step='question',
                               question=user.security_question,
                               error='Please enter your answer.')

    if answer != (user.security_answer or '').strip().lower():
        return render_template('forgot_password.html',
                               step='question',
                               question=user.security_question,
                               error='Incorrect answer. Please try again.')

    # Mark answer as verified in session
    session['sq_verified'] = True
    return render_template('forgot_password.html', step='reset')


@app.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Step 3 – save the new password.
    """
    if not session.get('sq_verified') or not session.get('reset_email'):
        return redirect('/forgot-password')

    email      = session.get('reset_email')
    new_pw     = request.form.get('password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if len(new_pw) < 6:
        return render_template('forgot_password.html', step='reset',
                               error='Password must be at least 6 characters.')

    if new_pw != confirm_pw:
        return render_template('forgot_password.html', step='reset',
                               error='Passwords do not match.')

    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect('/forgot-password')

    user.password = generate_password_hash(new_pw)
    db.session.commit()

    # Clear reset session keys
    session.pop('reset_email', None)
    session.pop('sq_verified', None)

    return render_template('login.html',
                           success='Password reset successful! You can now login.')


# ════════════════════════════════════════════════════════════════════════════
#  CART ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/cart')
def cart():
    if not session.get('user_id'):
        return redirect('/login')
    return render_template('cart.html')


@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    data       = request.get_json()
    product_id = data['product_id']
    product    = Product.query.get(product_id)
    if not product or product.stock <= 0:
        return jsonify({'error': 'Product out of stock'}), 400

    cart_obj = Cart.query.filter_by(user_id=session['user_id']).first()
    if not cart_obj:
        cart_obj = Cart(user_id=session['user_id'])
        db.session.add(cart_obj)
        db.session.commit()

    item = CartItem.query.filter_by(cart_id=cart_obj.id, product_id=product_id).first()
    if item:
        if item.quantity >= product.stock:
            return jsonify({'error': 'Not enough stock available'}), 400
        item.quantity += 1
    else:
        item = CartItem(cart_id=cart_obj.id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    return jsonify({'message': 'Added to cart'})


@app.route('/get-cart')
def get_cart():
    if not session.get('user_id'):
        return jsonify([])
    cart_obj = Cart.query.filter_by(user_id=session['user_id']).first()
    if not cart_obj:
        return jsonify([])
    items  = CartItem.query.filter_by(cart_id=cart_obj.id).all()
    result = []
    for item in items:
        product = Product.query.get(item.product_id)
        if product:
            result.append({
                'id':    item.id,
                'name':  product.name,
                'price': product.price,
                'qty':   item.quantity,
                'image': product.image or 'default.png',
                'stock': product.stock
            })
    return jsonify(result)


@app.route('/update-cart', methods=['POST'])
def update_cart():
    data = request.get_json()
    item = CartItem.query.get(data['id'])
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    product = Product.query.get(item.product_id)
    if data['action'] == 'increase':
        if product and item.quantity >= product.stock:
            return jsonify({'error': 'Max stock reached'}), 400
        item.quantity += 1
    elif data['action'] == 'decrease':
        if item.quantity > 1:
            item.quantity -= 1
        else:
            db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'updated'})


@app.route('/remove-item', methods=['POST'])
def remove_item():
    data = request.get_json()
    item = CartItem.query.get(data['id'])
    if item:
        db.session.delete(item)
        db.session.commit()
    return jsonify({'status': 'deleted'})


# ════════════════════════════════════════════════════════════════════════════
#  DELIVERY RADIUS CHECK
# ════════════════════════════════════════════════════════════════════════════

@app.route('/check-delivery-range', methods=['POST'])
def check_delivery_range():
    data     = request.get_json()
    user_lat = data.get('lat')
    user_lng = data.get('lng')
    store    = get_store()
    if not store.lat or not store.lng:
        return jsonify({'in_range': True, 'message': 'Store location not configured.'})
    dist = haversine_km(store.lat, store.lng, user_lat, user_lng)
    in_range = dist <= store.radius_km
    return jsonify({'in_range': in_range, 'distance_km': round(dist, 2),
                    'max_km': store.radius_km})


# ════════════════════════════════════════════════════════════════════════════
#  CHECKOUT & ORDERS
# ════════════════════════════════════════════════════════════════════════════

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not session.get('user_id'):
        return redirect('/login')
    if request.method == 'POST':
        user     = User.query.get(session['user_id'])
        cart_obj = Cart.query.filter_by(user_id=user.id).first()
        if not cart_obj:
            return redirect('/cart')
        items = CartItem.query.filter_by(cart_id=cart_obj.id).all()
        if not items:
            return redirect('/cart')

        address  = request.form.get('address', '')
        phone    = request.form.get('phone', '')
        user_lat = request.form.get('latitude')
        user_lng = request.form.get('longitude')

        total = 0
        for ci in items:
            p = Product.query.get(ci.product_id)
            if p:
                total += p.price * ci.quantity

        order = Order(
            user_id     = user.id,
            total_price = total,
            address     = address,
            phone       = phone,
            user_lat    = float(user_lat) if user_lat else None,
            user_lng    = float(user_lng) if user_lng else None,
        )
        db.session.add(order)
        db.session.flush()

        for ci in items:
            p = Product.query.get(ci.product_id)
            if p:
                db.session.add(OrderItem(
                    order_id   = order.id,
                    product_id = p.id,
                    quantity   = ci.quantity,
                    price      = p.price
                ))
                p.stock = max(0, p.stock - ci.quantity)
            db.session.delete(ci)

        db.session.commit()
        return redirect('/orders')

    user = User.query.get(session['user_id'])
    return render_template('checkout.html',
                           user=user,
                           razorpay_key=razorpay_key_id,
                           store_lat=get_setting('store_lat',''),
                           store_lng=get_setting('store_lng',''),
                           delivery_radius=DELIVERY_RADIUS_KM)


@app.route('/orders')
def orders():
    if not session.get('user_id'):
        return redirect('/login')
    user_orders = Order.query.filter_by(
        user_id=session['user_id']).order_by(Order.id.desc()).all()
    return render_template('orders.html', orders=user_orders)


@app.route('/order-items/<int:order_id>')
def order_items(order_id):
    items = OrderItem.query.filter_by(order_id=order_id).all()
    result = []
    for i in items:
        p = Product.query.get(i.product_id)
        if p:
            result.append({'name': p.name, 'qty': i.quantity, 'price': i.price})
    return jsonify(result)


@app.route('/place-order', methods=['POST'])
def place_order():
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    try:
        data     = request.get_json()
        address  = data.get('address', '')
        phone    = data.get('phone', '')
        user_lat = data.get('user_lat')
        user_lng = data.get('user_lng')

        user     = User.query.get(session['user_id'])
        cart_obj = Cart.query.filter_by(user_id=user.id).first()
        if not cart_obj:
            return jsonify({'error': 'Cart is empty'}), 400
        items = CartItem.query.filter_by(cart_id=cart_obj.id).all()
        if not items:
            return jsonify({'error': 'Cart is empty'}), 400

        total = 0
        for ci in items:
            p = Product.query.get(ci.product_id)
            if p:
                total += p.price * ci.quantity

        order = Order(
            user_id     = user.id,
            total_price = total,
            address     = address,
            phone       = phone,
            user_lat    = float(user_lat) if user_lat else None,
            user_lng    = float(user_lng) if user_lng else None,
            status      = 'Pending',
        )
        db.session.add(order)
        db.session.flush()

        for ci in items:
            p = Product.query.get(ci.product_id)
            if p:
                db.session.add(OrderItem(
                    order_id   = order.id,
                    product_id = p.id,
                    quantity   = ci.quantity,
                    price      = p.price
                ))
                p.stock = max(0, p.stock - ci.quantity)
            db.session.delete(ci)

        db.session.commit()

        # Try to create Razorpay order
        try:
            rzp_order = client.order.create({
                'amount':   int(total * 100),
                'currency': 'INR',
                'receipt':  f'order_{order.id}'
            })
            return jsonify({
                'order_id':    rzp_order['id'],
                'db_order_id': order.id,
                'amount':      total
            })
        except Exception:
            # Razorpay failed — still return success for COD
            return jsonify({
                'order_id':    None,
                'db_order_id': order.id,
                'amount':      total
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/payment-success', methods=['POST'])
def payment_success():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    data         = request.get_json()
    db_order_id  = data.get('db_order_id')
    payment_id   = data.get('payment_id', '')
    order        = Order.query.get(db_order_id)
    if order:
        order.payment_id = payment_id
        db.session.commit()
    return jsonify({'status': 'ok'})


# ════════════════════════════════════════════════════════════════════════════
#  TRACKING
# ════════════════════════════════════════════════════════════════════════════

@app.route('/track')
def track():
    if not session.get('user_id'):
        return redirect('/login')
    order = Order.query.filter_by(
        user_id=session['user_id'], status='Pending').order_by(Order.id.desc()).first()
    return render_template('track.html', order=order)


# ════════════════════════════════════════════════════════════════════════════
#  DELIVERY ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/delivery')
def delivery():
    if session.get('role') != 'delivery':
        return redirect('/')
    orders = Order.query.filter_by(status='Pending').order_by(Order.id.desc()).all()
    store_lat = get_setting('store_lat', '')
    store_lng = get_setting('store_lng', '')
    return render_template('delivery.html',
                           orders=orders,
                           store_lat=store_lat,
                           store_lng=store_lng)


@app.route('/deliver-order/<int:order_id>')
def deliver_order(order_id):
    if session.get('role') != 'delivery':
        return redirect('/')
    order = Order.query.get_or_404(order_id)
    order.status = 'Delivered'
    db.session.commit()
    return redirect('/delivery')


@app.route('/delivery-items/<int:order_id>')
def delivery_items(order_id):
    if session.get('role') != 'delivery':
        return jsonify({'error': 'Unauthorized'}), 403
    items = OrderItem.query.filter_by(order_id=order_id).all()
    result = []
    for i in items:
        p = Product.query.get(i.product_id)
        if p:
            result.append({'name': p.name, 'qty': i.quantity, 'price': i.price})
    return jsonify(result)


@app.route('/update-location', methods=['POST'])
def update_location():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    lat  = data.get('lat')
    lng  = data.get('lng')
    user = User.query.get(session['user_id'])
    if user:
        user.latitude  = lat
        user.longitude = lng
        if session.get('role') == 'delivery':
            pending_orders = Order.query.filter_by(status='Pending').all()
            for order in pending_orders:
                order.delivery_lat = lat
                order.delivery_lng = lng
    db.session.commit()
    return jsonify({'status': 'updated'})


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect('/')
    return render_template('admin_dashboard.html',
        total_users     = User.query.count(),
        total_products  = Product.query.count(),
        total_orders    = Order.query.count(),
        pending_orders  = Order.query.filter_by(status='Pending').count(),
        delivery_agents = User.query.filter_by(role='delivery').count()
    )


@app.route('/admin/products')
def admin_products():
    if session.get('role') != 'admin':
        return redirect('/')
    products      = Product.query.all()
    store_lat     = get_setting('store_lat', '')
    store_lng     = get_setting('store_lng', '')
    store_address = get_setting('store_address', '')
    return render_template('admin_products.html',
                           products=products,
                           store_lat=store_lat,
                           store_lng=store_lng,
                           store_address=store_address,
                           delivery_radius=DELIVERY_RADIUS_KM)


@app.route('/admin/add-product', methods=['POST'])
def admin_add_product():
    if session.get('role') != 'admin':
        return redirect('/')
    p = Product(
        name     = request.form['name'],
        price    = float(request.form['price']),
        category = request.form.get('category', ''),
        image    = request.form.get('image', 'default.png'),
        stock    = int(request.form.get('stock', 100))
    )
    db.session.add(p)
    db.session.commit()
    return redirect('/admin/products')


@app.route('/admin/delete-product/<int:id>')
def admin_delete_product(id):
    if session.get('role') != 'admin':
        return redirect('/')
    p = Product.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return redirect('/admin/products')


@app.route('/admin/edit-product/<int:id>', methods=['POST'])
def admin_edit_product(id):
    if session.get('role') != 'admin':
        return redirect('/')
    p          = Product.query.get_or_404(id)
    p.name     = request.form.get('name', p.name)
    p.price    = float(request.form.get('price', p.price))
    p.category = request.form.get('category', p.category)
    p.stock    = int(request.form.get('stock', p.stock))
    p.image    = request.form.get('image', p.image)
    db.session.commit()
    return redirect('/admin/products')


@app.route('/admin/save-store', methods=['POST'])
def admin_save_store():
    if session.get('role') != 'admin':
        return redirect('/')
    set_setting('store_address', request.form.get('store_address', ''))
    set_setting('store_lat',     request.form.get('store_lat', ''))
    set_setting('store_lng',     request.form.get('store_lng', ''))
    return redirect('/admin/products')


@app.route('/admin/orders')
def admin_orders():
    if session.get('role') != 'admin':
        return redirect('/')
    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin_orders.html', orders=orders)


@app.route('/update-order/<int:id>')
def update_order(id):
    if session.get('role') != 'admin':
        return redirect('/')
    order        = Order.query.get_or_404(id)
    order.status = 'Delivered'
    db.session.commit()
    return redirect('/admin/orders')


@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'admin':
        return redirect('/')
    users        = User.query.order_by(User.id).all()
    order_counts = {u.id: Order.query.filter_by(user_id=u.id).count() for u in users}
    users_data   = [
        {'id': u.id, 'name': u.name, 'email': u.email,
         'role': u.role, 'latitude': u.latitude, 'longitude': u.longitude, 'phone': u.phone}
        for u in users
    ]
    return render_template('admin_users.html',
                           users=users,
                           users_data=users_data,
                           order_counts=order_counts)


@app.route('/admin/delete-user/<int:id>')
def admin_delete_user(id):
    if session.get('role') != 'admin':
        return redirect('/')
    if id == session.get('user_id'):
        return redirect('/admin/users')
    u = User.query.get_or_404(id)
    if u.role == 'admin':
        return redirect('/admin/users')
    db.session.delete(u)
    db.session.commit()
    return redirect('/admin/users')


@app.route('/admin/order-items/<int:order_id>')
def admin_order_items(order_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    items = OrderItem.query.filter_by(order_id=order_id).all()
    return jsonify([
        {'name': Product.query.get(i.product_id).name, 'qty': i.quantity, 'price': i.price}
        for i in items if Product.query.get(i.product_id)
    ])


# also keep the /order-items/<id> alias used by customer orders page
# (already defined above as order_items)


# ════════════════════════════════════════════════════════════════════════════
#  SEED DATA
# ════════════════════════════════════════════════════════════════════════════

def seed_data():
    if Product.query.count() == 0:
        db.session.add_all([
            Product(name='Fresh Milk 1L',     price=58,  category='Dairy',      image='default.png', stock=100),
            Product(name='Basmati Rice 1kg',  price=95,  category='Grains',     image='default.png', stock=200),
            Product(name='Red Apple',         price=130, category='Fruits',     image='default.png', stock=50),
            Product(name='Whole Wheat Bread', price=45,  category='Bakery',     image='default.png', stock=80),
            Product(name='Farm Eggs 12pc',    price=75,  category='Dairy',      image='default.png', stock=150),
            Product(name='Tomatoes 500g',     price=35,  category='Vegetables', image='default.png', stock=120),
            Product(name='Paneer 200g',       price=85,  category='Dairy',      image='default.png', stock=60),
            Product(name='Banana Bunch',      price=40,  category='Fruits',     image='default.png', stock=90),
        ])

    if not User.query.filter_by(email='ram@gmail.com').first():
        db.session.add(User(
            name     = 'ram',
            email    = 'ram@gmail.com',
            password = generate_password_hash('ram123'),
            role     = 'admin'
        ))

    if not User.query.filter_by(email='krish@gmail.com').first():
        db.session.add(User(
            name     = 'krish',
            email    = 'krish@gmail.com',
            password = generate_password_hash('krish123'),
            role     = 'delivery'
        ))

    db.session.commit()


# ════════════════════════════════════════════════════════════════════════════
#  INIT
# ════════════════════════════════════════════════════════════════════════════

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import smtplib
from email.message import EmailMessage
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = '#' #Add your own key

# ---------- DATABASE ----------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///solare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- DATABASE MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items = db.Column(db.Text)  
    total = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='orders')


class ContactRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    daily_usage = db.Column(db.Float, nullable=False)
    off_grid = db.Column(db.String(10), nullable=False)
    products = db.Column(db.Text)  
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ---------- SAMPLE PRODUCTS ----------
products = [
    {'id': 1, 'name': 'Solar Panels', 'price': 5.00, 'image': r"static/Solar_panel.jpg", 'delivery': '2 days'},
    {'id': 2, 'name': 'Solar Inverter', 'price': 15.00, 'image': r"static/inverter.jpg", 'delivery': '5 days'},
    {'id': 3, 'name': 'Cables', 'price': 1.00, 'image': r"static/cabless.webp", 'delivery': '3 days'}
]

# ---------- HELPER: LOGIN REQUIRED ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- HELPER: SEND RECEIPT ----------
def send_invoice_email(customer_email, order_items, total_amount):
    item_rows = ""
    for item in order_items:
        item_rows += f"""
        <tr>
            <td style="padding:10px;border:1px solid #ddd;"><strong>{item['name']}</strong></td>
            <td style="padding:10px;border:1px solid #ddd;text-align:center;">{item['quantity']}</td>
            <td style="padding:10px;border:1px solid #ddd;text-align:right;">R{item['price']:.2f}</td>
            <td style="padding:10px;border:1px solid #ddd;text-align:right;">R{item['price']*item['quantity']:.2f}</td>
        </tr>
        """
    html_content = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f5f6fa;padding:20px;">
        <div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:15px;box-shadow:0 5px 15px rgba(0,0,0,0.1);">
            <h2 style="color:#0a74da;">Solare</h2>
            <p>Thank you for your order! Here’s your receipt:</p>
            <table style="width:100%;border-collapse:collapse;margin-top:20px;">
                <thead>
                    <tr>
                        <th style="padding:10px;border:1px solid #ddd;background:#0a74da;color:#fff;">Product</th>
                        <th style="padding:10px;border:1px solid #ddd;background:#0a74da;color:#fff;">Quantity</th>
                        <th style="padding:10px;border:1px solid #ddd;background:#0a74da;color:#fff;">Price</th>
                        <th style="padding:10px;border:1px solid #ddd;background:#0a74da;color:#fff;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {item_rows}
                </tbody>
            </table>
            <h3 style="text-align:right;margin-top:20px;">Total: R{total_amount:.2f}</h3>
            <p style="margin-top:30px;">We appreciate your business!</p>
        </div>
    </body>
    </html>
    """
    msg = EmailMessage()
    msg['Subject'] = "Your Receipt from Solare"
    msg['From'] = "#"  # replace with your email
    msg['To'] = customer_email
    msg.set_content("Thank you for your order! Your email client does not support HTML emails.")
    msg.add_alternative(html_content, subtype='html')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('#', 'mjdydkvmasjqeoyk')  # replace with app password
            smtp.send_message(msg)
        print(f"Receipt sent to {customer_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ---------- ROUTES ----------

@app.route('/')
def index():
    return render_template('index.html', products=products, cart=session.get('cart', []))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.form['product_id'])
    cart = session.get('cart', [])
    for item in cart:
        if item['id'] == product_id:
            item['quantity'] += 1
            break
    else:
        product = next((p for p in products if p['id'] == product_id), None)
        if product:
            cart.append({'id': product['id'], 'name': product['name'], 'price': product['price'], 'quantity': 1})
    session['cart'] = cart
    return jsonify({'cart_count': sum(item['quantity'] for item in cart)})

@app.route('/cart', methods=['GET','POST'])
@login_required
def cart_page():
    cart = session.get('cart', [])
    total_amount = sum(item['price']*item['quantity'] for item in cart)
    if request.method == 'POST':
        for item in cart:
            qty = request.form.get(f'quantity_{item["id"]}')
            if qty:
                item['quantity'] = max(1, int(qty))
        session['cart'] = cart
        flash("Cart updated!", "success")
        return redirect(url_for('cart_page'))
    return render_template('cart.html', cart=cart, total_amount=total_amount)




@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    cart = session.get('cart', [])
    total_amount = sum(item['price']*item['quantity'] for item in cart)
    username = session.get('username')
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found. Please log in again.", "error")
        session.pop('username', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.get_json()
        payment_ref = data.get('reference')  

        # --- Save order ---
        order = Order(user_id=user.id, items=json.dumps(cart), total=total_amount)
        db.session.add(order)
        db.session.commit()

        # Clear cart & send receipt
        send_invoice_email(user.email, cart, total_amount)
        session['cart'] = []
        flash("Payment successful! Order placed and receipt sent.", "success")
        return jsonify({"status": "success"})

    return render_template('checkout.html', cart=cart, total_amount=total_amount, customer_email=user.email)


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return redirect(url_for('register'))
        new_user = User(username=username, password=password, email=email)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        flash("Registration successful!", "success")
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        flash("Invalid username or password.", "error")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/calculator', methods=['GET', 'POST'])
def calculator():
    recommendations = []
    total_kwh = None
    if request.method == 'POST':
        # ---------- User selections ----------
        appliances = request.form.getlist('appliances')  # list of appliance names
        fully_offgrid = request.form.get('offgrid') == 'yes'

        # ---------- Typical daily kWh usage per appliance ----------
        appliance_kwh = {
            'Fridge': 1.5,
            'Freezer': 1.5,
            'TV': 0.1,
            'Laptop': 0.05,
            'Desktop PC': 0.15,
            'Microwave': 0.12,
            'Oven': 1.0,
            'Electric kettle': 0.12,
            'Lights': 0.5,
            'Washing Machine': 0.5,
            'Dishwasher': 1.2,
            'Fan': 0.2,
            'Heater': 2.0,
            'Air Conditioner': 3.0,
            'Charging Phones': 0.02
        }

        # ---------- Calculate total daily kWh ----------
        total_kwh = sum(appliance_kwh[a] for a in appliances if a in appliance_kwh)
        if fully_offgrid:
            total_kwh *= 1.2  # add 20% buffer for off-grid reliability

        # ---------- Generate product recommendations ----------
        if total_kwh <= 3:
            recommendations.append('Small 1kW Solar Panel Kit')
            recommendations.append('Basic Inverter 1kW')
            recommendations.append('Small Battery 5kWh')
        elif total_kwh <= 6:
            recommendations.append('Medium 3kW Solar Panel Kit')
            recommendations.append('Inverter 3kW')
            recommendations.append('Battery 10kWh')
        else:
            recommendations.append('Large 5kW+ Solar Panel Kit')
            recommendations.append('Inverter 5kW+')
            recommendations.append('Battery 20kWh+')

    # ---------- Household appliance list ----------
    appliance_list = [
        'Fridge', 'Freezer', 'TV', 'Laptop', 'Desktop PC', 'Microwave', 'Oven',
        'Electric kettle', 'Lights', 'Washing Machine', 'Dishwasher', 'Fan',
        'Heater', 'Air Conditioner', 'Charging Phones'
    ]

    return render_template(
        'calculator.html',
        appliance_list=appliance_list,
        total_kwh=total_kwh,
        recommendations=recommendations
    )


    return render_template('calculator.html')

@app.route('/consultation', methods=['POST'])
@login_required
def consultation():
    username = session.get('username')
    user = User.query.filter_by(username=username).first()
    
    
    print(f"Consultation requested by {user.username} ({user.email})")  # placeholder
    
    flash("Thank you! We will contact you soon.", "success")
    return redirect(url_for('calculator'))



@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out.", "success")
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

# ---------- ADMIN DASHBOARD ----------
@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('username') != 'admin':
        flash("Access denied.", "error")
        return redirect(url_for('index'))

    users = User.query.all()
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    for order in orders:
        order.parsed_items = json.loads(order.items)
    return render_template('admin.html', users=users, orders=orders)

# ---------- MAIN ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # --- create admin user if it doesn't exist ---
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='admin', email='admin@example.com')
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True)

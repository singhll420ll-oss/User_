from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dp_filename = db.Column(db.String(200))
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100))
    location = db.Column(db.String(200))
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    image = db.Column(db.String(200))
    short_description = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    available_till = db.Column(db.DateTime)
    
    # Relationship
    items = db.relationship('ServiceItem', backref='service', lazy=True)

class ServiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    item_description = db.Column(db.Text)

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(200))
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'))
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='cart_items')
    service = db.relationship('Service')
    menu = db.relationship('Menu')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON string of items
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    payment_method = db.Column(db.String(50))
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='orders')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(200))
    description = db.Column(db.Text, nullable=False)
    sent_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        user = User.query.filter_by(mobile=mobile).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_dp'] = user.dp_filename
            return redirect(url_for('dashboard'))
        else:
            # User doesn't exist, redirect to registration
            return redirect(url_for('register'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Handle file upload
        dp_file = request.files.get('dp')
        dp_filename = None
        if dp_file:
            filename = secure_filename(dp_file.filename)
            dp_filename = f"dp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            dp_file.save(os.path.join(app.config['UPLOAD_FOLDER'], dp_filename))
        
        # Get form data
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        location = request.form.get('location')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return "Passwords do not match", 400
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            dp_filename=dp_filename,
            name=name,
            mobile=mobile,
            email=email,
            location=location,
            password=hashed_password
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Auto login
            session['user_id'] = new_user.id
            session['user_name'] = new_user.name
            session['user_dp'] = new_user.dp_filename
            
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            return "Registration failed", 400
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get all data for dashboard
    services = Service.query.all()
    menus = Menu.query.all()
    cart_items = Cart.query.filter_by(user_id=user_id).all()
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    user = User.query.get(user_id)
    messages = Message.query.filter_by(is_active=True).order_by(Message.sent_time.desc()).all()
    
    # Calculate cart total
    cart_total = 0
    for item in cart_items:
        if item.service:
            price = item.service.price - item.service.discount
        elif item.menu:
            price = item.menu.price - item.menu.discount
        cart_total += price * item.quantity
    
    return render_template('dashboard.html',
                         services=services,
                         menus=menus,
                         cart_items=cart_items,
                         orders=orders,
                         user=user,
                         messages=messages,
                         cart_total=cart_total)

@app.route('/service/<int:service_id>')
def service_details(service_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    service = Service.query.get_or_404(service_id)
    return render_template('service_details.html', service=service)

@app.route('/order_form')
def order_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    
    if not cart_items:
        return redirect(url_for('dashboard'))
    
    return render_template('order_form.html', user=user)

@app.route('/api/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.json
    item_type = data.get('type')  # 'service' or 'menu'
    item_id = data.get('id')
    
    cart_item = None
    if item_type == 'service':
        cart_item = Cart(user_id=session['user_id'], service_id=item_id)
    elif item_type == 'menu':
        cart_item = Cart(user_id=session['user_id'], menu_id=item_id)
    
    if cart_item:
        db.session.add(cart_item)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/api/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    data = request.json
    cart_id = data.get('cart_id')
    action = data.get('action')  # 'increase', 'decrease', 'remove'
    
    cart_item = Cart.query.get(cart_id)
    if not cart_item or cart_item.user_id != session['user_id']:
        return jsonify({'success': False})
    
    if action == 'increase':
        cart_item.quantity += 1
    elif action == 'decrease':
        cart_item.quantity -= 1
        if cart_item.quantity <= 0:
            db.session.delete(cart_item)
    elif action == 'remove':
        db.session.delete(cart_item)
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/submit_order', methods=['POST'])
def submit_order():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    user_id = session['user_id']
    data = request.json
    
    # Get cart items
    cart_items = Cart.query.filter_by(user_id=user_id).all()
    
    # Prepare items data
    items_data = []
    total_price = 0
    
    for item in cart_items:
        if item.service:
            item_price = item.service.price - item.service.discount
            items_data.append({
                'type': 'service',
                'name': item.service.name,
                'quantity': item.quantity,
                'price': item_price
            })
            total_price += item_price * item.quantity
        elif item.menu:
            item_price = item.menu.price - item.menu.discount
            items_data.append({
                'type': 'menu',
                'name': item.menu.name,
                'quantity': item.quantity,
                'price': item_price
            })
            total_price += item_price * item.quantity
    
    # Create order
    order = Order(
        user_id=user_id,
        items=json.dumps(items_data),
        total_price=total_price,
        payment_method=data.get('payment_method'),
        location=data.get('location', '')
    )
    
    try:
        db.session.add(order)
        # Clear cart
        Cart.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'success': True, 'order_id': order.id})
    except:
        db.session.rollback()
        return jsonify({'success': False})

@app.route('/api/get_location')
def get_location():
    # This would integrate with GPS in production
    # For demo, return a mock location
    return jsonify({
        'success': True,
        'location': 'Demo Location, City, State'
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

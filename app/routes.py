from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Event, Member
from datetime import datetime
import socket
import qrcode
import io
import base64

bp = Blueprint('main', __name__)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

@bp.route('/invite')
def invite():
    # Generate the URL dynamically
    # Use PUBLIC_URL env var if available (useful for production override)
    # Otherwise use the request's URL root which works with ProxyFix
    import os
    if os.environ.get('PUBLIC_URL'):
        url = os.environ.get('PUBLIC_URL')
    else:
        # If running locally (no proxy usually), get_local_ip might still be useful
        # but for Render, request.url_root with ProxyFix is best.
        # We'll use a hybrid approach: if strictly local IP is needed for
        # cross-device testing on LAN, we keep get_local_ip logic for debug mode.
        from flask import current_app
        if current_app.debug:
             ip_address = get_local_ip()
             url = f"http://{ip_address}:5000"
        else:
             url = url_for('main.index', _external=True)
    
    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for HTML display
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    qr_b64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
    
    return render_template('invite.html', qr_code=qr_b64, url=url)


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('¡Registro exitoso! Por favor inicia sesión.', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash('Error: El usuario o correo ya existe.', 'danger')
            
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user is None or not user.check_password(password):
            flash('Correo o contraseña incorrectos.', 'danger')
            return redirect(url_for('main.login'))
        
        login_user(user)
        return redirect(url_for('main.dashboard'))
        
    return render_template('login.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    events = Event.query.order_by(Event.date.asc()).all()
    return render_template('dashboard.html', user=current_user, events=events)

@bp.route('/events')
@login_required
def events():
    events = Event.query.order_by(Event.date.asc()).all()
    return render_template('events.html', events=events)

@bp.route('/events/new', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date_str = request.form['date']
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de fecha inválido.', 'danger')
            return redirect(url_for('main.create_event'))

        event = Event(title=title, description=description, date=date_obj, author=current_user)
        
        try:
            db.session.add(event)
            db.session.commit()
            flash('Evento creado exitosamente.', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el evento.', 'danger')
            
    return render_template('create_event.html')

@bp.route('/members')
@login_required
def members():
    members = Member.query.order_by(Member.last_name.asc()).all()
    return render_template('members.html', members=members)

@bp.route('/members/new', methods=['GET', 'POST'])
@login_required
def new_member():
    if request.method == 'POST':
        try:
            member = Member(
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                phone=request.form['phone'],
                email=request.form['email'],
                address=request.form['address'],
                status=request.form.get('status', 'Activo')
            )
            
            if request.form['birthdate']:
                member.birthdate = datetime.strptime(request.form['birthdate'], '%Y-%m-%d')
                
            db.session.add(member)
            db.session.commit()
            flash('Miembro registrado exitosamente.', 'success')
            return redirect(url_for('main.members'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar miembro: {str(e)}', 'danger')
            
    return render_template('member_form.html', member=None)

@bp.route('/members/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    member = Member.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            member.first_name = request.form['first_name']
            member.last_name = request.form['last_name']
            member.phone = request.form['phone']
            member.email = request.form['email']
            member.address = request.form['address']
            member.status = request.form['status']
            
            if request.form['birthdate']:
                member.birthdate = datetime.strptime(request.form['birthdate'], '%Y-%m-%d')
            else:
                member.birthdate = None
                
            db.session.commit()
            flash('Información actualizada.', 'success')
            return redirect(url_for('main.members'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')
            
    return render_template('member_form.html', member=member)

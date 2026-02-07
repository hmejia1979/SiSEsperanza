import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Usuario, Casa, Pago, Gasto
from dotenv import load_dotenv
from sqlalchemy import func
load_dotenv()

app = Flask(__name__)
print("Ruta del proyecto:", os.getcwd())
print("¿Existe la carpeta static?:", os.path.exists('static'))
print("¿Existe el archivo CSS?:", os.path.exists('static/css/style.css'))
import os
app = Flask(__name__, static_folder='static', static_url_path='/static')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/')
def index():
    # Si el usuario no está logueado, lo mandamos al login
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(username=username).first()
        
        # Por ahora, sin encriptación para que pruebes rápido
        if user and user.password == password:
            login_user(user)
            if user.rol == 'admin':
                return redirect(url_for('registrar_pago'))
            else:
                return redirect(url_for('ver_estado_cuenta')) # Esta la crearemos luego
        
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# RUTA DE REGISTRO DE PAGOS (SOLO ADMIN)
@app.route('/admin/registrar-pago', methods=['GET', 'POST'])
@login_required
def registrar_pago(): # <--- Este nombre debe ser único en todo el archivo
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))

    if request.method == 'POST':
        c_id = request.form.get('casa_id')
        m_valor = request.form.get('monto')
        c_concepto = request.form.get('concepto')

        try:
            nuevo_pago = Pago(
                monto=float(m_valor), 
                concepto=c_concepto, 
                casa_id=int(c_id)
            )
            db.session.add(nuevo_pago)
            db.session.commit()
            flash("¡Pago registrado exitosamente!")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar: {str(e)}")
        
        return redirect(url_for('registrar_pago'))

    casas = Casa.query.all()
    # Esta línea es la que agregamos para la nueva tabla
    pagos_recientes = Pago.query.order_by(Pago.id.desc()).limit(10).all()
    
    return render_template('admin/registrar_pago.html', 
                           casas=casas, 
                           pagos_recientes=pagos_recientes)

@app.route('/admin/crear-dueno', methods=['GET', 'POST'])
@login_required
def crear_dueno():
    if current_user.rol != 'admin':
        return "Acceso denegado", 403

    if request.method == 'POST':
        numero_casa = request.form.get('numero_casa')
        nombre_dueno = request.form.get('nombre')
        deuda_inicial = request.form.get('deuda_2025', 0)
        username = request.form.get('username')
        password = request.form.get('password')

        # 1. Crear la Casa
        nueva_casa = Casa(
            numero_casa=numero_casa, 
            dueno_nombre=nombre_dueno, 
            deuda_2025=float(deuda_inicial)
        )
        db.session.add(nueva_casa)
        db.session.flush() # Esto genera el ID de la casa antes de guardar

        # 2. Crear el Usuario para ese dueño
        nuevo_usuario = Usuario(
            username=username,
            password=password, # Idealmente usaría bcrypt después
            rol='dueno',
            casa_id=nueva_casa.id
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash(f'Casa {numero_casa} y usuario {username} creados con éxito')
        return redirect(url_for('registrar_pago'))

    return render_template('admin/crear_dueno.html')

@app.route('/admin/reporte-morosos')
@login_required
def reporte_morosos():
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))

    casas = Casa.query.all()
    reporte = []

    for casa in casas:
        # Sumamos todos los pagos de esta casa
        total_pagado = sum(pago.monto for pago in casa.pagos)
        saldo_pendiente = float(casa.deuda_2025 or 0) - float(total_pagado or 0)
        
        # Solo lo agregamos si queremos ver a todos, 
        # o puedes filtrar solo los que tienen saldo > 0
        reporte.append({
            'numero': casa.numero_casa,
            'propietario': casa.dueno_nombre,
            'total_deuda': casa.deuda_2025,
            'pagado': total_pagado,
            'saldo': saldo_pendiente
        })

    return render_template('admin/reporte_morosos.html', reporte=reporte)
@app.route('/admin/registrar-gasto', methods=['GET', 'POST'])
@login_required
def registrar_gasto():
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))

    if request.method == 'POST':
        desc = request.form.get('descripcion')
        monto = request.form.get('monto')
        cat = request.form.get('categoria')

        nuevo_gasto = Gasto(
            descripcion=desc,
            monto=float(monto),
            categoria=cat
        )
        db.session.add(nuevo_gasto)
        db.session.commit()
        flash("Gasto registrado con éxito")
        return redirect(url_for('registrar_gasto'))

    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()
    total_gastos = sum(g.monto for g in gastos)
    
    return render_template('admin/registrar_gasto.html', gastos=gastos, total_gastos=total_gastos)

@app.route('/mi-estado')
@login_required
def ver_estado_cuenta():
    # Buscamos la casa vinculada al usuario actual
    casa = Casa.query.get(current_user.casa_id)
    
    if not casa:
        return "No tienes una casa asignada. Contacta al administrador.", 404

    # Calculamos el total de pagos sumando la columna 'monto'
    total_pagado = sum(float(p.monto) for p in casa.pagos)
    
    # SALDO FINAL = (Deuda 2025) - (Pagos realizados)
    saldo_pendiente = casa.deuda_2025 - total_pagado

    return render_template('dueno/estado_cuenta.html', 
                           casa=casa, 
                           total_pagado=total_pagado, 
                           saldo_pendiente=saldo_pendiente)

@app.route('/admin/reporte')
@login_required
def reporte_general():
    if current_user.rol != 'admin':
        return "Acceso denegado", 403
    
    # Suma total de todos los pagos registrados en la historia
    total_recaudado = db.session.query(func.sum(Pago.monto)).scalar() or 0
    # Lista de todas las casas con sus respectivos saldos
    casas = Casa.query.all()
    
    return render_template('admin/reporte.html', total=total_recaudado, casas=casas)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Crea las tablas en Postgres automáticamente
    app.run(debug=True)

if __name__ == '__main__':
    with app.app_context():
        # 1. Crea las tablas si no existen
        db.create_all() 
        
        # 2. Buscamos si ya existe el admin
        admin_existente = Usuario.query.filter_by(username='admin').first()
        
        if not admin_existente:
            print("--- CREANDO USUARIO ADMINISTRADOR DE PRUEBA ---")
            nuevo_admin = Usuario(
                username='admin', 
                password='123', 
                rol='admin'
            )
            db.session.add(nuevo_admin)
            db.session.commit()
            print("--- ADMIN CREADO EXITOSAMENTE (user: admin / pass: 123) ---")
        else:
            print(f"--- EL ADMIN YA EXISTE: {admin_existente.username} ---")
            
    app.run(debug=True)
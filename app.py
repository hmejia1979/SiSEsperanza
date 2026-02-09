import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Usuario, Casa, Pago, Gasto
from dotenv import load_dotenv
from sqlalchemy import func
from datetime import datetime
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
    # Esto quita el error de LegacyAPIWarning
    return db.session.get(Usuario, int(user_id))
@app.route('/')
@login_required
def inicio():
    if current_user.rol == 'admin':
        # 1. Calculamos los datos (asegurándonos de definir las variables)
        total_ingresos = db.session.query(db.func.sum(Pago.monto)).scalar() or 0
        total_egresos = db.session.query(db.func.sum(Gasto.monto)).scalar() or 0
        balance = float(total_ingresos) - float(total_egresos)

        # 2. Consultar gastos para la gráfica
        gastos_query = db.session.query(
            Gasto.categoria, db.func.sum(Gasto.monto)
        ).group_by(Gasto.categoria).all()

        labels = [str(g[0]) for g in gastos_query]
        valores = [float(g[1]) for g in gastos_query]

        # 3. Enviamos TODAS las variables al HTML
        return render_template('admin/inicio_admin.html', 
                               ingresos=total_ingresos, 
                               egresos=total_egresos, 
                               balance=balance,
                               labels=labels,
                               valores=valores)
    
    return redirect(url_for('ver_estado_cuenta'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Cambiamos 'email' por 'username'
        username = request.form.get('username') 
        password = request.form.get('password')
        
        # Buscamos en la base de datos por el campo 'username'
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.password == password: # Nota: Luego deberías usar hash para seguridad
            login_user(usuario)
            return redirect(url_for('inicio'))
        else:
            # Aquí podrías usar flash() para avisar que los datos son incorrectos
            return "Usuario o contraseña incorrectos"
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# RUTA DE REGISTRO DE PAGOS (SOLO ADMIN)
@app.route('/admin/registrar-pago', methods=['GET', 'POST'])
@login_required
def registrar_pago():
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))

    if request.method == 'POST':
        c_id = request.form.get('casa_id')
        m_valor = request.form.get('monto')
        c_concepto = request.form.get('concepto')

        try:
            monto_float = float(m_valor)
            casa_id_int = int(c_id)
            
            # 1. Creamos el registro del pago
            nuevo_pago = Pago(
                monto=monto_float, 
                concepto=c_concepto, 
                casa_id=casa_id_int
            )
            
            # 2. BUSCAMOS LA CASA Y RESTAMOS LA DEUDA
            casa = Casa.query.get(casa_id_int)
            if casa:
                casa.deuda_2025 -= monto_float # <--- ¡Aquí ocurre la magia!
            
            db.session.add(nuevo_pago)
            db.session.commit()
            flash("¡Pago registrado y deuda actualizada!")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar: {str(e)}")
        
        return redirect(url_for('registrar_pago'))

    casas = Casa.query.all()
    pagos_recientes = Pago.query.order_by(Pago.id.desc()).limit(10).all()
    
    # Ajusté la ruta del template (quité 'admin/') si tus archivos están en templates directamente
    return render_template('/admin/registrar_pago.html', 
                           casas=casas, 
                           pagos_recientes=pagos_recientes)

@app.route('/admin/generar-mensualidad', methods=['POST'])
@login_required
def generar_mensualidad():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))

    # Valor fijo de la cuota mensual
    CUOTA_FIJA = 5.00
    
    # Obtenemos el nombre del mes actual para el mensaje de confirmación
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_actual = meses[datetime.now().month - 1]

    try:
        casas = Casa.query.all()
        if not casas:
            flash("No hay casas registradas.")
            return redirect(url_for('lista_casas'))

        for casa in casas:
            # Sumamos los 5 dólares a la deuda actual
            casa.deuda_2025 += CUOTA_FIJA
        
        db.session.commit()
        flash(f"✅ Se han cargado ${CUOTA_FIJA:.2f} a todas las casas (Mes: {mes_actual})")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al generar mensualidad: {str(e)}")

    return redirect(url_for('lista_casas'))

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

@app.route('/admin/casas')
@login_required
def lista_casas():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    # Cambiamos Casa.numero por Casa.numero_casa
    todas_las_casas = Casa.query.order_by(Casa.numero_casa).all()
    return render_template('/admin/casas.html', casas=todas_las_casas)

@app.route('/admin/registrar-casa', methods=['GET', 'POST'])
@login_required
def registrar_casa():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        numero = request.form.get('numero')
        bloque = request.form.get('bloque')
        
        nueva_casa = Casa(numero=numero, bloque=bloque)
        try:
            db.session.add(nueva_casa)
            db.session.commit()
            return redirect(url_for('lista_casas'))
        except:
            db.session.rollback()
            return "Error: Ese número de casa ya existe."
            
    return render_template('registrar_casa.html')

@app.route('/admin/propietarios')
@login_required
def lista_propietarios():
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))
    
    # Obtenemos todos los usuarios que son dueños
    propietarios = Usuario.query.filter_by(rol='propietario').all()
    return render_template('propietarios.html', propietarios=propietarios) 

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

@app.route('/admin/registrar-usuario', methods=['GET', 'POST'])
@login_required
def registrar_usuario():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    
    # Obtenemos todas las casas para mostrarlas en el formulario
    casas_disponibles = Casa.query.all()
    
    if request.method == 'POST':
        username = request.form.get('nombre')
        password = request.form.get('password')
        casa_id = request.form.get('casa_id') # Tomamos el valor del 'select'
        
        nuevo_usuario = Usuario(
            username=username,
            password=password,
            rol='propietario',
            casa_id=casa_id
        )
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            return redirect(url_for('lista_propietarios'))
        except Exception as e:
            db.session.rollback()
            return f"Error al guardar: {e}"
        
    # Pasamos las casas al template
    return render_template('/admin/registrar_usuario.html', casas=casas_disponibles)



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

@app.route('/admin/editar-propietario/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_propietario(id):
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    
    usuario = Usuario.query.get_or_404(id)
    casas_disponibles = Casa.query.all()
    
    if request.method == 'POST':
        usuario.username = request.form.get('nombre')
        usuario.casa_id = request.form.get('casa_id')
        if request.form.get('password'):
            usuario.password = request.form.get('password')
            
        db.session.commit()
        return redirect(url_for('lista_propietarios'))
    
    return render_template('/admin/editar_propietario.html', usuario=usuario, casas=casas_disponibles)



@app.route('/admin/eliminar-propietario/<int:id>')
@login_required
def eliminar_propietario(id):
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    
    usuario = Usuario.query.get_or_404(id)
    try:
        db.session.delete(usuario)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"No se puede eliminar: el usuario tiene registros asociados. {e}"
        
    return redirect(url_for('lista_propietarios'))


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
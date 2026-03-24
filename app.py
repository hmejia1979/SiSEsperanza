import os
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import func
from fpdf import FPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Modelos
from models import db, Usuario, Casa, Pago, Gasto, RegistroCarga

load_dotenv()


load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # <--- ¡ESTO ES VITAL!

@login_manager.user_loader
def load_user(user_id):
    # Esto quita el error de LegacyAPIWarning
    return db.session.get(Usuario, int(user_id))

@app.route('/')
def index():
    # Esta función decide qué es lo primero que ve el usuario
    if current_user.is_authenticated:
        # Si ya inició sesión anteriormente
        return redirect(url_for('inicio'))
    else:
        # Si es un usuario nuevo o no se ha identificado
        return redirect(url_for('login'))
    
@app.route('/inicio')
@login_required
def inicio():
    if current_user.rol == 'admin':
        # 1. Cálculos de Totales (lo que ya tenías)
        total_ingresos = db.session.query(db.func.sum(Pago.monto)).scalar() or 0
        total_egresos = db.session.query(db.func.sum(Gasto.monto)).scalar() or 0
        balance = float(total_ingresos) - float(total_egresos)

        # 2. Datos para la gráfica (lo que ya tenías)
        gastos_query = db.session.query(Gasto.categoria, db.func.sum(Gasto.monto)).group_by(Gasto.categoria).all()
        labels = [str(g[0]) if g[0] else "Varios" for g in gastos_query]
        valores = [float(g[1]) for g in gastos_query]

        # 3. NUEVO: Obtener los últimos 5 movimientos mezclados
        ultimos_pagos = Pago.query.order_by(Pago.id.desc()).limit(5).all()
        ultimos_gastos = Gasto.query.order_by(Gasto.id.desc()).limit(5).all()
        
        movimientos = []
        for p in ultimos_pagos:
            movimientos.append({'fecha': p.fecha, 'tipo': 'PAGO', 'descripcion': f"Casa {p.casa.numero_casa}", 'monto': p.monto})
        for g in ultimos_gastos:
            movimientos.append({'fecha': g.fecha, 'tipo': 'GASTO', 'descripcion': g.descripcion, 'monto': g.monto})
        
        # Ordenamos por fecha descendente y tomamos solo los 5 más nuevos
        movimientos = sorted(movimientos, key=lambda x: x['fecha'], reverse=True)[:5]

        return render_template('admin/inicio_admin.html', 
                               ingresos=total_ingresos, 
                               egresos=total_egresos, 
                               balance=balance,
                               labels=labels,
                               valores=valores,
                               movimientos=movimientos, # Enviamos la lista
                               current_time=datetime.now())
    
    return redirect(url_for('mi_estado'))

from datetime import datetime

@app.route('/admin/generar-alicuotas-mes', methods=['POST'])
@login_required
def generar_alicuotas():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))

    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = hoy.year

    # 1. Verificar si ya se generó este mes
    ya_existe = RegistroCarga.query.filter_by(mes=mes_actual, anio=anio_actual).first()

    if ya_existe:
        flash(f"⚠️ ¡Atención! Ya se generaron las alícuotas para {mes_actual}/{anio_actual} el día {ya_existe.fecha_ejecucion.strftime('%d/%m')}.")
        return redirect(url_for('pagos_globales'))

    try:
        # 2. Si no existe, procedemos a cargar la deuda
        VALOR_ALICUOTA = 5.00
        todas_las_casas = Casa.query.all()
        
        for casa in todas_las_casas:
            deuda_actual = casa.deuda_2025 or 0.0
            casa.deuda_2025 = deuda_actual + VALOR_ALICUOTA
        
        # 3. Guardamos el registro de que ya se hizo este mes
        nuevo_registro = RegistroCarga(mes=mes_actual, anio=anio_actual)
        db.session.add(nuevo_registro)
        
        db.session.commit()
        flash(f"🚀 Éxito: Se cargaron ${VALOR_ALICUOTA} a todas las casas para el mes {mes_actual}.")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error crítico: {str(e)}")

    return redirect(url_for('pagos_globales'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(username=username).first()
        
        # Esta es la parte clave:
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('¡Bienvenido de nuevo!')
            return redirect(url_for('inicio'))
        else:
            flash('Usuario o contraseña incorrectos')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    from flask_login import logout_user
    logout_user() # Borra la sesión del navegador
    flash("Has cerrado sesión correctamente.")
    return redirect(url_for('login'))


# RUTA DE REGISTRO DE PAGOS (SOLO ADMIN)
@app.route('/admin/registrar-pago', methods=['GET', 'POST'])
@login_required
def registrar_pago():
    # 1. Seguridad: Solo el admin puede entrar aquí
    if current_user.rol != 'admin':
        flash("No tienes permiso para realizar esta acción.")
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        c_id = request.form.get('casa_id')
        m_valor = request.form.get('monto')
        c_concepto = request.form.get('concepto')

        # Verificamos que los datos no estén vacíos
        if not c_id or not m_valor:
            flash("Error: Seleccione una casa y un monto válido.")
            return redirect(url_for('registrar_pago'))

        try:
            monto_float = float(m_valor)
            casa_id_int = int(c_id)
            
            # 2. BUSCAMOS LA CASA PARA ACTUALIZAR SU DEUDA
            casa_seleccionada = Casa.query.get(casa_id_int)
            
            if casa_seleccionada:
                # REGLA CONTABLE: Deuda Actual - Pago Realizado = Nueva Deuda
                # Ejemplo: Debe 5 y paga 5 -> 5 - 5 = 0 (Al día)
                # Ejemplo: Debe 0 y paga 5 -> 0 - 5 = -5 (Saldo a favor)
                casa_seleccionada.deuda_2025 -= monto_float

                # 3. CREAMOS EL REGISTRO DEL PAGO EN EL HISTORIAL
                nuevo_pago = Pago(
                    monto=monto_float, 
                    concepto=c_concepto, 
                    casa_id=casa_id_int
                )
                
                db.session.add(nuevo_pago)
                db.session.commit()
                flash(f"¡Pago de ${monto_float} registrado a la Casa {casa_seleccionada.numero_casa}!")
            else:
                flash("Error: La casa seleccionada no existe.")

        except Exception as e:
            db.session.rollback()
            flash(f"Error técnico al procesar el pago: {str(e)}")
        
        return redirect(url_for('pagos_globales'))

    # 4. PREPARAR DATOS PARA LA VISTA (GET)
    # Listamos todas las casas para el menú desplegable
    casas = Casa.query.order_by(Casa.numero_casa.asc()).all()
    # Traemos los últimos 10 pagos para la tabla de la derecha
    pagos_recientes = Pago.query.order_by(Pago.id.desc()).limit(10).all()
    
    return render_template('/admin/registrar_pago.html', 
                           casas=casas, 
                           pagos_recientes=pagos_recientes)





@app.route('/admin/descargar-recibo/<int:pago_id>')
@login_required
def descargar_recibo(pago_id):
    pago = db.session.get(Pago, pago_id)
    casa = db.session.get(Casa, pago.casa_id)
    
    pdf_buffer = generar_recibo_pdf(pago, casa)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"Recibo_Casa_{casa.numero_casa}.pdf",
        mimetype='application/pdf'
    )


def generar_recibo_pdf(pago, casa):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Diseño del Recibo
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "🏘️ SiSEsperanza - Comprobante de Pago")
    
    p.setFont("Helvetica", 12)
    p.line(100, 740, 500, 740)
    
    p.drawString(100, 710, f"Recibo N°: 000{pago.id}")
    p.drawString(100, 690, f"Fecha: {pago.fecha.strftime('%d/%m/%Y')}")
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, 650, "DATOS DEL PROPIETARIO:")
    p.setFont("Helvetica", 12)
    p.drawString(100, 630, f"Nombre: {casa.dueno_nombre}")
    p.drawString(100, 610, f"Casa N°: {casa.numero_casa}")
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 560, f"MONTO PAGADO: ${pago.monto}")
    
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, 500, "Este documento sirve como soporte legal de su pago mensual.")
    p.drawString(100, 485, "Gracias por mantener sus cuotas al día.")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer

@app.route('/admin/registrar-casa', methods=['GET', 'POST'])
@login_required
def registrar_casa():
    if request.method == 'POST':
        # 1. Obtenemos los datos del formulario (lo que dice name="...")
        print("DATOS RECIBIDOS:", request.form)
        num = request.form.get('numero_casa')
        nombre = request.form.get('propietario') # <-- ¿Coincide con el HTML?
        deuda = request.form.get('deuda_inicial')
        u_id = request.form.get('usuario_id')

        # 2. Creamos el objeto Casa
        # IMPORTANTE: Los nombres a la IZQUIERDA del '=' deben ser 
        # IGUALES a los de tu class Casa(db.Model)
        nueva_casa = Casa(
            numero_casa=num,
            dueno_nombre=nombre,      # <--- AQUÍ ESTABA EL POSIBLE ERROR
            deuda_2025=float(deuda) if deuda else 0.0,
            usuario_id=int(u_id) if u_id and u_id != "" else None
        )
        
        try:
            db.session.add(nueva_casa)
            db.session.commit()
            flash(f"✅ Casa {num} guardada con éxito.")
            return redirect(url_for('lista_casas'))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al guardar: {str(e)}")
            return redirect(url_for('registrar_casa'))

    propietarios = Usuario.query.filter_by(rol='propietario').all()
    return render_template('admin/registrar_casa.html', usuarios=propietarios)


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



@app.route('/admin/propietarios')
@login_required
def lista_propietarios():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))

    # Traemos a todos los usuarios que tienen el rol de 'usuario'
    # .all() es fundamental para obtener la lista
    lista_users = Usuario.query.filter_by(rol='propietario').all()
    todos = Usuario.query.all()
    print(f"Total en DB: {len(todos)} | Roles encontrados: {[u.rol for u in todos]}")
    return render_template('propietarios.html', propietarios=lista_users)
 

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

    if request.method == 'POST':
        # Capturamos TODO lo que viene del HTML
        username = request.form.get('username')
        password = request.form.get('password')
        cedula = request.form.get('cedula')
        telefono = request.form.get('telefono')
        casa_id = request.form.get('casa_id') # El ID de la casa elegida

        # Creamos el usuario con todos sus datos
        nuevo_usuario = Usuario(
            username=username,
            password=generate_password_hash(password),
            cedula=cedula,
            telefono=telefono,
            rol='propietario'
        )
        
        db.session.add(nuevo_usuario)
        db.session.flush() # Esto "pre-guarda" para obtener el ID del usuario

        # Si eligió una casa, la vinculamos de una vez
        if casa_id:
            casa = Casa.query.get(casa_id)
            if casa:
                casa.usuario_id = nuevo_usuario.id
        
        db.session.commit()
        flash("✅ Propietario creado y vinculado correctamente.")
        return redirect(url_for('lista_propietarios'))

    # Para el GET: Solo mostramos casas que no tienen dueño
    casas_disponibles = Casa.query.filter_by(usuario_id=None).all()
    return render_template('admin/registrar_usuario.html', casas=casas_disponibles)

@app.route('/admin/registrar-gasto', methods=['GET', 'POST'])
@login_required
def registrar_gasto():
    if current_user.rol != 'admin':
        return redirect(url_for('ver_estado_cuenta'))

    if request.method == 'POST':
        desc = request.form.get('descripcion')
        monto = request.form.get('monto')
        cat = request.form.get('categoria')
        recibo = request.form.get('numero_recibo') # <--- NUEVO: Captura el recibo

        nuevo_gasto = Gasto(
            descripcion=desc,
            monto=float(monto),
            categoria=cat,
            numero_recibo=recibo # <--- NUEVO: Asegúrate que tu clase Gasto tenga este campo
        )
        db.session.add(nuevo_gasto)
        db.session.commit()
        flash("✅ Gasto registrado con éxito")
        return redirect(url_for('registrar_gasto'))

    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()
    total_gastos = sum(g.monto for g in gastos)
    return render_template('admin/registrar_gasto.html', gastos=gastos, total_gastos=total_gastos)

from fpdf import FPDF
from flask import send_file
import os

@app.route('/admin/descargar-pdf-gastos')
@login_required
def descargar_pdf_gastos():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))

    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Encabezado
    pdf.cell(190, 10, "SISTEMA SIS ESPERANZA", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(190, 10, "Informe Detallado de Gastos", ln=True, align='C')
    pdf.ln(10)

    # Tabla: Encabezados
    pdf.set_fill_color(30, 41, 59) # Color azul oscuro (como tu tema)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, " Fecha", 1, 0, 'C', True)
    pdf.cell(70, 10, " Descripcion", 1, 0, 'C', True)
    pdf.cell(30, 10, " Recibo", 1, 0, 'C', True)
    pdf.cell(30, 10, " Categoria", 1, 0, 'C', True)
    pdf.cell(30, 10, " Monto", 1, 1, 'C', True)

    # Tabla: Datos
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    total = 0
    for g in gastos:
        pdf.cell(30, 10, g.fecha.strftime('%d/%m/%Y'), 1)
        pdf.cell(70, 10, g.descripcion[:35], 1)
        pdf.cell(30, 10, str(g.numero_recibo or 'N/A'), 1)
        pdf.cell(30, 10, str(g.categoria), 1)
        pdf.cell(30, 10, f"${g.monto:,.2f}", 1, 1, 'R')
        total += g.monto

    # Total Final
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(160, 10, "TOTAL DE GASTOS REALIZADOS: ", 1, 0, 'R')
    pdf.cell(30, 10, f"${total:,.2f}", 1, 1, 'R')

    # Guardado temporal y envío
    output_path = os.path.join('instance', 'informe_gastos.pdf')
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

@app.route('/admin/editar-propietario/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_propietario(id):
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))
    
    usuario = db.session.get(Usuario, id)
    if not usuario:
        flash("Usuario no encontrado")
        return redirect(url_for('lista_propietarios'))

    if request.method == 'POST':
        usuario.username = request.form.get('username')
        nueva_pass = request.form.get('password')
        nueva_casa_id = request.form.get('casa_id')
        usuario.username = request.form.get('username')
        usuario.cedula = request.form.get('cedula')     # <-- Captura cédula
        usuario.telefono = request.form.get('telefono') # <-- Captura teléfono
        usuario.correo = request.form.get('correo') 
        # 1. Actualizar contraseña si se escribió una
        if nueva_pass and nueva_pass.strip() != "":
            usuario.password = generate_password_hash(nueva_pass)
            
        # 2. Actualizar vinculación de casa
        # Primero quitamos al usuario de su casa actual (si tenía una)
        casa_actual = Casa.query.filter_by(usuario_id=usuario.id).first()
        if casa_actual:
            casa_actual.usuario_id = None
        
        # Luego lo asignamos a la nueva casa seleccionada
        if nueva_casa_id:
            nueva_casa = db.session.get(Casa, int(nueva_casa_id))
            if nueva_casa:
                nueva_casa.usuario_id = usuario.id
            
        db.session.commit()
        flash("Datos y vinculación actualizados correctamente")
        
        return redirect(url_for('lista_propietarios'))

    # Buscamos casas libres + la casa que ya tiene este usuario
    casas_disponibles = Casa.query.filter((Casa.usuario_id == None) | (Casa.usuario_id == usuario.id)).all()
    
    return render_template('admin/editar_propietario.html', usuario=usuario, casas=casas_disponibles)

@app.route('/admin/pagos-globales')
@login_required
def pagos_globales():
    if current_user.rol != 'admin':
        return redirect(url_for('inicio'))

    todos_los_pagos = Pago.query.order_by(Pago.id.desc()).all()
    total_recaudado = sum(pago.monto for pago in todos_los_pagos)

    # Enviamos la fecha actual para el encabezado del reporte
    return render_template('admin/pagos_globales.html', 
                           pagos=todos_los_pagos, 
                           total=total_recaudado,
                           current_time=datetime.now())

@app.route('/admin/editar-casa/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_casa(id):
    casa = Casa.query.get_or_404(id)
    
    if request.method == 'POST':
        casa.numero_casa = request.form.get('numero_casa')
        casa.dueno_nombre = request.form.get('propietario') # El 'name' de tu HTML
        casa.deuda_2025 = float(request.form.get('deuda_inicial') or 0)
        
        # Actualizamos el vínculo con el usuario
        u_id = request.form.get('usuario_id')
        casa.usuario_id = int(u_id) if u_id and u_id != "" else None
        
        db.session.commit()
        flash("🏠 Casa actualizada correctamente")
        return redirect(url_for('lista_casas'))

    # --- ESTA ES LA PARTE QUE FALTA ---
    # Buscamos a todos los propietarios para que aparezcan en la lista desplegable
    propietarios_disponibles = Usuario.query.filter_by(rol='propietario').all()
    
    return render_template('admin/editar_casa.html', 
                           casa=casa, 
                           usuarios=propietarios_disponibles) # Enviamos la lista

@app.route('/admin/eliminar-casa/<int:id>', methods=['POST'])
@login_required
def eliminar_casa(id):
    if current_user.rol != 'admin':
        flash("No tienes permiso para realizar esta acción.")
        return redirect(url_for('inicio'))

    # Usamos el método moderno db.session.get
    casa = db.session.get(Casa, id)
    
    if casa:
        try:
            # Importante: Si la casa tiene pagos asociados, SQLAlchemy 
            # los manejará según cómo definiste la relación (backref).
            db.session.delete(casa)
            db.session.commit()
            flash(f"La Casa {casa.numero_casa} ha sido eliminada.")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al eliminar: {str(e)}")
    else:
        flash("La casa no existe.")

    return redirect(url_for('lista_casas'))

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
def mi_estado():
    # Buscamos la casa vinculada directamente al ID del usuario logueado
    casa = Casa.query.filter_by(usuario_id=current_user.id).first()
    
    if not casa:
        flash("Tu cuenta de usuario aún no tiene una propiedad asignada. Contacta al administrador.")
        return redirect(url_for('inicio'))

    return render_template('estado_cuenta.html', casa=casa, pagos=casa.pagos)

@app.route('/mi-cuenta')
@login_required
def mi_cuenta():
    # 1. Buscamos la casa que le pertenece al usuario logueado
    # Usamos dueno_nombre porque así se llama en tu modelo Casa
    casa = Casa.query.filter_by(dueno_nombre=current_user.nombre).first()

    if not casa:
        # Si no lo encuentra por nombre, el administrador debe verificar 
        # que el nombre del usuario y el 'dueno_nombre' sean idénticos.
        flash("No se encontró una propiedad vinculada a su cuenta.")
        return redirect(url_for('inicio'))

    # 2. Obtenemos los pagos usando la relación que definiste: casa.pagos
    # Esto busca automáticamente en la tabla Pagos todos los que tengan el casa_id de esta casa
    mis_pagos = casa.pagos

    return render_template('estado_cuenta.html', casa=casa, pagos=casa.pagos)


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
        # Crea las tablas con la estructura limpia
        db.create_all()
        
        # Buscamos si ya existe el admin para no repetirlo
        admin_check = Usuario.query.filter_by(username='admin').first()
        
        if not admin_check:
            from werkzeug.security import generate_password_hash
            hashed_pw = generate_password_hash('admin123')
            
            # Creamos el único admin oficial
            admin_maestro = Usuario(
                username='admin',
                password=hashed_pw,
                rol='admin'
            )
            db.session.add(admin_maestro)
            db.session.commit()
            print("✅ SISTEMA LIMPIO: Admin creado (user: admin / pass: admin123)")
        else:
            print("ℹ️ El sistema ya tiene un administrador.")

    app.run(debug=True)
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from flask_mail import Mail, Message

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='propietario')
    
    # --- NUEVOS CAMPOS ---
    cedula = db.Column(db.String(15), unique=True, nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    correo = db.Column(db.String(100), nullable=True) # Opcional, pero muy útil


class Casa(db.Model):
    __tablename__ = 'casas'
    id = db.Column(db.Integer, primary_key=True)
    numero_casa = db.Column(db.String(10), unique=True, nullable=False)
    dueno_nombre = db.Column(db.String(100)) # Nombre real para mostrar
    saldo_total = db.Column(db.Float, default=0.0)
    # EL CAMBIO CLAVE: Vincular con el ID del usuario
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    propietario_user = db.relationship('Usuario', backref='casa', uselist=False)
    pagos = db.relationship('Pago', backref='casa', lazy=True, cascade="all, delete-orphan")


class Gasto(db.Model):
    __tablename__ = 'gastos'
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ESTAS SON LAS QUE PROBABLEMENTE FALTAN:
    categoria = db.Column(db.String(50), nullable=True) 
    numero_recibo = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Gasto {self.descripcion}>'
    
class RegistroCarga(db.Model):
    __tablename__ = 'registros_carga' # Opcional, pero recomendado
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    fecha_ejecucion = db.Column(db.DateTime, default=datetime.utcnow)
    
class Configuracion(db.Model):
    __tablename__ = 'configuraciones' # Opcional, pero recomendado
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False) 
    valor = db.Column(db.Float, nullable=False)

class Deuda(db.Model):
    __tablename__ = 'deudas'
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    mes = db.Column(db.Integer, nullable=False)  # Guarda 1, 2, 3...
    anio = db.Column(db.Integer, nullable=False) # Guarda 2026...
    pagado = db.Column(db.Boolean, default=False)
    casa_id = db.Column(db.Integer, db.ForeignKey('casas.id'), nullable=False)

    # ESTA ES LA FUNCIÓN QUE CORRIGE EL ERROR
    @property
    def nombre_mes(self):
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        # Retorna el nombre según el número, o "Desconocido" si no existe
        return meses.get(self.mes, "Mes Desconocido")
    

class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    casa_id = db.Column(db.Integer, db.ForeignKey('casas.id'), nullable=False)
    deuda_id = db.Column(db.Integer, db.ForeignKey('deudas.id'), nullable=True)
    # concepto = db.Column(db.String(200)) # Usa esto en lugar de 'nota' si prefieres
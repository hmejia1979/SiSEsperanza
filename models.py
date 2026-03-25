from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

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
    deuda_2025 = db.Column(db.Float, default=0.0)
    # EL CAMBIO CLAVE: Vincular con el ID del usuario
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    propietario_user = db.relationship('Usuario', backref='casa', uselist=False)
    pagos = db.relationship('Pago', backref='casa', lazy=True, cascade="all, delete-orphan")


class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    concepto = db.Column(db.String(100))
    casa_id = db.Column(db.Integer, db.ForeignKey('casas.id'), nullable=False)

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
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    fecha_ejecucion = db.Column(db.DateTime, default=datetime.utcnow)
    
class Configuracion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False) # Ej: 'valor_alicuota'
    valor = db.Column(db.Float, nullable=False)
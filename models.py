from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Casa(db.Model):
    __tablename__ = 'casas'
    id = db.Column(db.Integer, primary_key=True)
    numero_casa = db.Column(db.String(10), unique=True, nullable=False)
    dueno_nombre = db.Column(db.String(100))
    deuda_2025 = db.Column(db.Float, default=0.0) # Lo pendiente del año pasado
    pagos = db.relationship('Pago', backref='casa', lazy=True)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False) # 'admin' o 'dueno'
    casa_id = db.Column(db.Integer, db.ForeignKey('casas.id'), nullable=True)

class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    concepto = db.Column(db.String(100))
    casa_id = db.Column(db.Integer, db.ForeignKey('casas.id'), nullable=False)

class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50))  # Ej: Servicios, Mantenimiento, Limpieza
    fecha = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f'<Gasto {self.descripcion}>'
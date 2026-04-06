# Crea un archivo llamado "arreglar_db.py" y ejecútalo una vez
from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE pagos ADD COLUMN nota VARCHAR(200)"))
        conn.commit()
    print("✅ Columna 'nota' agregada con éxito.")
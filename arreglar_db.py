from app import app, db

with app.app_context():
    try:
        # Esto añade la columna directamente a tu base de datos de PostgreSQL
        db.session.execute(db.text('ALTER TABLE casas ADD COLUMN deuda_anterior FLOAT DEFAULT 0.0;'))
        db.session.commit()
        print("✅ Columna 'deuda_anterior' añadida con éxito.")
    except Exception as e:
        print(f"❌ Error o la columna ya existía: {e}")
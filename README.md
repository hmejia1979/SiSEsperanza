# SiSEsperanza

Sistema de gestión para conjunto residencial (Flask, PostgreSQL, reportes Excel/PDF, correo y cobros programados).

## Stack de producción


- **Flask** + Gunicorn
- **PostgreSQL 16**
- **Docker Swarm** + **Traefik** (HTTPS)
- **GitHub Actions** → **GHCR** → VPS Linux

## Requisitos en el VPS

1. Docker en modo Swarm (`docker swarm init` si aplica).
2. Red overlay externa para Traefik:

```bash
docker network create --driver=overlay traefik-public
```

3. Traefik con entrypoint `https` y resolver TLS `letsencrypt` (ajustar nombres en `stack.yml` si tu Traefik usa otros).
4. Directorio de despliegue:

```bash
sudo mkdir -p /opt/sise
sudo chown $USER:$USER /opt/sise
```

5. Archivo `.env` en `/opt/sise/.env` (copiar desde `.env.example` y completar valores reales).

## Secretos de GitHub

Configurar en **Settings → Secrets and variables → Actions**:

| Secret | Descripción |
|--------|-------------|
| `VPS_HOST` | IP o dominio del VPS |
| `VPS_USER` | Usuario SSH |
| `VPS_PASSWORD` | Contraseña SSH |
| `VPS_SSH_PORT` | Puerto SSH (ej. `22`) |
| `GHCR_PATH` | Personal Access Token con `write:packages` y `read:packages` |

## Flujo CI/CD

```text
git push origin main   (o rama final)
        ↓
GitHub Actions: build → push GHCR
        ↓
SCP stack.yml → VPS
        ↓
docker stack deploy --with-registry-auth -c stack.yml sise
        ↓
https://siseesperanza.byronrm.com
```

## Despliegue manual

```bash
# Build local
make build VERSION=1.0.0

# Login GHCR
echo TOKEN | docker login ghcr.io -u byronmoreno --password-stdin

make push VERSION=1.0.0

# En el VPS (con .env cargado)
cd /opt/sise
make deploy
```

## Comandos útiles (Makefile)

| Comando | Acción |
|---------|--------|
| `make build` | Construir imagen |
| `make push` | Subir a GHCR |
| `make deploy` | `docker stack deploy` |
| `make logs` | Logs del servicio app |
| `make restart` | Reiniciar app |
| `make rollback` | Rollback del servicio app |
| `make status` | Estado del stack |
| `make remove` | Eliminar stack |

## Desarrollo local

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Editar DATABASE_URL, SECRET_KEY, correo...
python app.py
```

## Variables de entorno

Ver `.env.example`. La app usa `DATABASE_URL` en local; en Swarm se construye desde `POSTGRES_*` en `stack.yml`.

## Notas

- Gunicorn usa **1 worker** para que APScheduler no ejecute tareas duplicadas.
- Tras el primer despliegue, inicializar tablas/admin: entrar al contenedor o ejecutar migraciones según tu proceso (`db.create_all()` en desarrollo).
- Si Traefik usa `websecure` en lugar de `https`, editar `entrypoints` en `stack.yml`.

## Dominio e imagen

- Dominio: `siseesperanza.byronrm.com`
- Imagen: `ghcr.io/byronmoreno/siseesperanza`
- Stack: `sise`

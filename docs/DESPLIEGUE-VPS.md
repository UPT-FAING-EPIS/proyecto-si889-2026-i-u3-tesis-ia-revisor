# Despliegue en VPS

Esta guia asume una VPS Linux con Nginx, systemd, Python 3.12+ y Node.js compatible con Next.js 16 (`>=20.9.0`). El despliegue recomendado es:

- Frontend Next.js en `127.0.0.1:3000`.
- Backend FastAPI en `127.0.0.1:8000`.
- Nginx como proxy publico con HTTPS.
- Supabase como base de datos, storage y auth.

No subas llaves reales al repositorio. Usa `backend/.env.local` para secretos del backend y `frontend/.env.production` para variables publicas del build de Next.js.

## 1. Dominios recomendados

Opcion recomendada para produccion:

```text
https://app.tudominio.com  -> frontend
https://api.tudominio.com  -> backend
```

Con esta opcion, el frontend debe compilarse con:

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.tudominio.com
```

Opcion de un solo dominio:

```text
https://tudominio.com          -> frontend
https://tudominio.com/backend  -> backend
```

Con esta opcion, el frontend debe compilarse con:

```bash
NEXT_PUBLIC_BACKEND_URL=/backend
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
```

No uses `NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000` en produccion. En el navegador del usuario eso apunta a la computadora del usuario, no a la VPS.

## 2. Variables de backend

Crea `backend/.env.local` en la VPS:

```bash
# Gemini
GEMINI_API_KEY=tu_api_key_de_gemini
# API_GEMINI tambien funciona como alias, pero usa solo una de las dos.
GEMINI_API_VERSION=v1
GEMINI_CHAT_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
GEMINI_EMBEDDING_OUTPUT_DIMENSIONALITY=3072
GEMINI_CHAT_MAX_OUTPUT_TOKENS=3072
GEMINI_REVIEW_MAX_OUTPUT_TOKENS=6144
GEMINI_REVIEW_MAX_INPUT_CHARS=260000

# DeepSeek, requerido solo si usaras ese proveedor desde la UI.
DEEPSEEK_API_KEY=tu_api_key_de_deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-v4-pro
DEEPSEEK_CHAT_MAX_OUTPUT_TOKENS=8192

# Supabase
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_PUBLISHABLE_KEY=tu_publishable_key
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key
SUPABASE_STORAGE_BUCKET=thesis-documents
SUPABASE_STORAGE_SIGNED_URL_EXPIRES_SECONDS=3600

# CORS
# Si usas subdominios:
CORS_ORIGINS=https://app.tudominio.com

# Si usas un solo dominio, cambia la linea anterior por:
# CORS_ORIGINS=https://tudominio.com
```

Variables criticas:

- `SUPABASE_SERVICE_ROLE_KEY`: requerida para crear usuarios sin verificacion de correo y para operaciones backend con RLS.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`: requeridas para auth y acceso a Supabase.
- `GEMINI_API_KEY` o `API_GEMINI`: requerida para generar embeddings y respuestas con Gemini.
- `DEEPSEEK_API_KEY`: requerida solo si eliges DeepSeek en la aplicacion.
- `CORS_ORIGINS`: debe coincidir exactamente con la URL publica del frontend.

## 3. Variables de frontend

Crea `frontend/.env.production` antes de ejecutar `npm run build`.

Para subdominios:

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.tudominio.com
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
```

Para un solo dominio con `/backend`:

```bash
NEXT_PUBLIC_BACKEND_URL=/backend
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
```

`NEXT_PUBLIC_BACKEND_URL` queda embebida en el build del frontend. Si la cambias, vuelve a ejecutar `npm run build` y reinicia el servicio del frontend.

## 4. Instalacion en la VPS

Ejemplo usando `/opt/proyecto-si889` como ruta de despliegue:

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip certbot python3-certbot-nginx
```

Instala Node.js `>=20.9.0` con el metodo que uses en tu servidor. Verifica:

```bash
node -v
npm -v
python3 --version
```

Clona o copia el proyecto:

```bash
sudo mkdir -p /opt/proyecto-si889
sudo chown -R $USER:$USER /opt/proyecto-si889
git clone <URL_DEL_REPOSITORIO> /opt/proyecto-si889
cd /opt/proyecto-si889
```

Prepara backend:

```bash
cd /opt/proyecto-si889/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
find app -name "*.py" -print0 | xargs -0 python -m py_compile
```

Prepara frontend:

```bash
cd /opt/proyecto-si889/frontend
npm ci
npm run build
```

## 5. Servicios systemd

Reemplaza `deploy` por el usuario real que ejecutara la app. Si instalaste Node con `nvm`, ajusta la ruta de `node`/`npm` porque systemd no carga tu shell interactiva.

Backend: `/etc/systemd/system/tesis-backend.service`

```ini
[Unit]
Description=Asesor IA de Tesis Backend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/proyecto-si889/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/proyecto-si889/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Frontend: `/etc/systemd/system/tesis-frontend.service`

```ini
[Unit]
Description=Asesor IA de Tesis Frontend
After=network.target tesis-backend.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/proyecto-si889/frontend
Environment=NODE_ENV=production
Environment=PORT=3000
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activa los servicios:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesis-backend
sudo systemctl enable --now tesis-frontend
sudo systemctl status tesis-backend --no-pager
sudo systemctl status tesis-frontend --no-pager
```

Pruebas locales en la VPS:

```bash
curl -sS http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000
```

## 6. Nginx con subdominios

Archivo sugerido: `/etc/nginx/sites-available/proyecto-si889`

```nginx
server {
    listen 80;
    server_name app.tudominio.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name api.tudominio.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activa Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/proyecto-si889 /etc/nginx/sites-enabled/proyecto-si889
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d app.tudominio.com -d api.tudominio.com
```

## 7. Nginx con un solo dominio

Usa esta variante solo si quieres publicar todo en `https://tudominio.com`.

```nginx
server {
    listen 80;
    server_name tudominio.com;

    client_max_body_size 50M;

    location /backend/ {
        rewrite ^/backend/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Activa HTTPS:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d tudominio.com
```

## 8. Verificacion final

Subdominios:

```bash
curl -sS https://api.tudominio.com/health
curl -I https://app.tudominio.com
```

Un solo dominio:

```bash
curl -sS https://tudominio.com/backend/health
curl -I https://tudominio.com
```

Luego prueba desde el navegador:

1. Crear cuenta con correo y contrasena.
2. Confirmar que entra al dashboard sin verificar correo.
3. Subir un PDF.
4. Hacer una pregunta en el chat.
5. Generar o descargar un plan de tesis si aplica.

## 9. Actualizar despliegue

```bash
cd /opt/proyecto-si889
git pull

cd backend
source .venv/bin/activate
pip install -r requirements.txt
find app -name "*.py" -print0 | xargs -0 python -m py_compile

cd ../frontend
npm ci
npm run build

sudo systemctl restart tesis-backend
sudo systemctl restart tesis-frontend
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Problemas comunes

- Registro crea usuario pero no inicia sesion: revisa `SUPABASE_SERVICE_ROLE_KEY` en `backend/.env.local`.
- Error CORS: `CORS_ORIGINS` no coincide con la URL publica exacta del frontend.
- Frontend intenta llamar a `127.0.0.1`: cambia `NEXT_PUBLIC_BACKEND_URL` y recompila con `npm run build`.
- Subida de PDF falla con 413: sube `client_max_body_size` en Nginx.
- Cambiaste variables `NEXT_PUBLIC_*`: recompila frontend y reinicia `tesis-frontend`.
- Cambiaste variables backend: reinicia `tesis-backend`.
- DeepSeek falla: confirma `DEEPSEEK_API_KEY`; Gemini puede funcionar aunque DeepSeek no este configurado.

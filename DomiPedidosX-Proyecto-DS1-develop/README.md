# DomiPedidosX

Aplicación web para la gestión de pedidos de restaurantes, desarrollada como proyecto académico para la asignatura **Desarrollo de Software I**.

El proyecto utiliza una arquitectura con frontend y backend separados:

- **Frontend:** React, Vite, Axios y Tailwind CSS.
- **Backend:** Python, Django, Django REST Framework, autenticación JWT (SimpleJWT) y WebSockets con Django Channels.
- **Base de datos:** PostgreSQL local para desarrollo y Supabase para producción.
- **Control de versiones:** Git y GitHub.

> **Estado actual:** el backend tiene los 30 modelos del diseño repartidos en 6 apps de Django (`sedes`, `usuarios`, `menu`, `inventario`, `promociones` y `pedidos`), con sus migraciones, pruebas y CI. El frontend tiene su estructura inicial. Las funcionalidades del sistema se desarrollan durante los sprints.

Documentación técnica del backend: [`docs/README.md`](docs/README.md). Normas de contribución: [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 1. Requisitos previos

Antes de comenzar, instala las siguientes herramientas.

| Herramienta | Uso |
|---|---|
| Git | Descargar el repositorio y gestionar los cambios. |
| Python 3.14.x | Ejecutar el backend. |
| pip | Instalar las dependencias de Python. |
| Node.js 22 LTS (22.12 o posterior) | Ejecutar las herramientas del frontend. |
| npm | Instalar las dependencias de JavaScript. |
| PostgreSQL 16 o posterior | Base de datos local para desarrollo y pruebas. |
| Editor de código | Se recomienda Visual Studio Code, aunque puedes utilizar otro. |

### 1.1. Instalar las herramientas en Linux

#### EndeavourOS y Arch Linux

Actualiza el sistema e instala las herramientas:

```bash
sudo pacman -Syu
sudo pacman -S --needed git python python-pip nodejs-lts-jod npm
```

El paquete `nodejs-lts-jod` proporciona Node.js 22 LTS.

#### Ubuntu y Debian

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

Después, instala una versión compatible de Node.js desde la página oficial:

https://nodejs.org/

Comprueba que la versión instalada sea compatible con Vite 8.

#### Fedora

```bash
sudo dnf install git python3 python3-pip
```

Asegúrate de contar también con `python3-venv` o el soporte de entornos virtuales que proporcione tu instalación de Python, y con una versión compatible de Node.js y npm.

Puedes obtener Node.js desde:

https://nodejs.org/

### 1.2. Instalar las herramientas en Windows

Abre PowerShell y utiliza WinGet para instalar las herramientas:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.14 -e
winget install --id OpenJS.NodeJS.LTS -e
```

Si Windows no reconoce los comandos después de instalar, cierra y vuelve a abrir la terminal.

### 1.3. Instalar las herramientas en macOS

Si tienes Homebrew instalado:

```bash
brew install git python@3.14
brew install node@22
```

Si algún paquete no está disponible para tu versión de Homebrew, consulta las instrucciones oficiales:

- Git: https://git-scm.com/downloads
- Python: https://www.python.org/downloads/
- Node.js: https://nodejs.org/
- Homebrew: https://brew.sh/

### 1.4. Verificar las instalaciones

Ejecuta los comandos disponibles en tu sistema:

```bash
git --version
python --version
python3 --version
node --version
npm --version
psql --version
```

En Windows también puedes comprobar Python con:

```powershell
py --version
```

**Importante:** las versiones de Python disponibles dependen del sistema operativo y de sus repositorios. El backend se preparó inicialmente con Python 3.14.8. Si utilizas otra versión de Python 3.14, verifica que las dependencias se instalen correctamente.

---

## 2. Clonar el repositorio

Abre una terminal y ejecuta:

```bash
git clone https://github.com/alejo2807/DomiPedidosX-Proyecto-DS1.git
cd DomiPedidosX-Proyecto-DS1
```

La rama de integración del equipo es `develop`.

Para obtener los cambios más recientes:

```bash
git switch develop
git pull origin develop
```

Si ya tienes el repositorio descargado, entra en su carpeta y ejecuta los comandos de actualización anteriores.

---

## 3. Configurar el backend

El backend se encuentra en la carpeta `backend/`.

### 3.1. Crear el entorno virtual

Ejecuta el comando correspondiente a tu sistema operativo desde la raíz del repositorio.

**Linux y macOS:**

```bash
python3 -m venv backend/.venv
```

**Windows — PowerShell:**

```powershell
py -3.14 -m venv backend/.venv
```

Si tu instalación de Windows utiliza `python` en lugar de `py`, puedes probar:

```powershell
python -m venv backend/.venv
```

No necesitas crear el entorno virtual si ya existe uno funcional en `backend/.venv/`. Cada integrante debe tener su propio entorno virtual local.

### 3.2. Activar el entorno virtual

**Linux y macOS:**

```bash
source backend/.venv/bin/activate
```

**Windows — PowerShell:**

```powershell
.\backend\.venv\Scripts\Activate.ps1
```

**Windows — Símbolo del sistema (CMD):**

```bat
backend\.venv\Scripts\activate.bat
```

Al activarse, normalmente aparecerá `(.venv)` al comienzo de la línea de comandos.

Si PowerShell bloquea la activación del entorno, puedes utilizar CMD o ejecutar Python directamente desde el entorno virtual.

### 3.3. Instalar las dependencias

Desde la raíz del repositorio, con el entorno virtual activado:

```bash
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

### 3.4. Configurar la base de datos local

Cada integrante usa **su propia base PostgreSQL local**. Nunca se trabaja ni se corren pruebas contra Supabase.

Instala PostgreSQL con las instrucciones oficiales de tu sistema (https://www.postgresql.org/download/) y crea un rol y una base. Cambia el nombre y la clave por los que prefieras:

```bash
sudo -u postgres psql -c "CREATE ROLE domipedidosx LOGIN PASSWORD 'cambia-esta-clave' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE domipedidosx OWNER domipedidosx;"
```

En Windows, ejecuta las mismas dos sentencias SQL desde `psql` o pgAdmin.

El permiso `CREATEDB` es necesario: `pytest` crea una base temporal llamada `test_<nombre>` en cada ejecución y la borra al terminar.

### 3.5. Configurar las variables de entorno

El proyecto lee su configuración (clave secreta, datos de la base de datos, etc.) desde un archivo `.env`. Ese archivo es personal y **nunca se sube a GitHub**.

Copia la plantilla y edítala con tus datos locales:

```bash
cp backend/.env.example backend/.env
```

En Windows (PowerShell): `Copy-Item backend\.env.example backend\.env`

Abre `backend/.env` y completa cada variable. La plantilla `.env.example` lista todas las que el proyecto necesita. Los datos de la base deben coincidir con el rol y la base que creaste en el paso anterior, y el host debe ser `localhost`.

> **Importante:** confirma que el `.env` apunta a tu base local y no a Supabase antes de migrar.

### 3.6. Crear las tablas

Con el entorno virtual activo, desde la raíz del repositorio:

```bash
python backend/manage.py check
python backend/manage.py migrate
```

Al terminar, tu base debe tener 39 tablas: 9 de Django y 30 propias del proyecto.

Si cambias un modelo, la migración va en el mismo Pull Request. Las reglas de migraciones están en [`CONTRIBUTING.md`](CONTRIBUTING.md).

### 3.7. Ejecutar las pruebas

Las pruebas se ejecutan desde la carpeta `backend/`:

```bash
cd backend
pytest
cd ..
```

Deben pasar antes de abrir un Pull Request. GitHub Actions las ejecuta de nuevo automáticamente en cada PR.

### 3.8. Ejecutar el servidor de desarrollo

Desde la raíz del repositorio:

```bash
python backend/manage.py runserver
```

El backend estará disponible normalmente en:

http://127.0.0.1:8000/

La documentación interactiva de la API (Swagger) está en http://127.0.0.1:8000/api/docs/ y el panel de administración en http://127.0.0.1:8000/admin/. Para crear un usuario administrador:

```bash
python backend/manage.py createsuperuser
```

El inicio de sesión del sistema usa el **correo electrónico** como identificador. Para detener el servidor, presiona `Ctrl + C`.

**WebSockets (HU-29):** el servidor de desarrollo usa Django Channels mediante ASGI. Si `REDIS_URL` no está configurada, se utiliza una capa en memoria adecuada para trabajar localmente con un solo proceso. En despliegues con varios procesos o instancias, configura Redis en `backend/.env`, por ejemplo `REDIS_URL=redis://127.0.0.1:6379/0`, para que todos reciban los eventos de pedidos.

---

## 4. Configurar el frontend

El frontend se encuentra en la carpeta `frontend/`.

### 4.1. Instalar las dependencias

Desde la raíz del repositorio:

```bash
cd frontend
npm ci
```

`npm ci` instala las dependencias utilizando `package-lock.json`, respetando las versiones registradas en el proyecto.

Si `npm ci` informa que falta o no coincide el archivo de bloqueo, no lo elimines ni lo regeneres automáticamente: informa al equipo para revisar el estado del repositorio.

### 4.2. Ejecutar el frontend

```bash
npm run dev
```

Vite mostrará una dirección local, normalmente:

http://localhost:5173/

Abre esa dirección en el navegador.

Para detener el servidor, presiona `Ctrl + C`.

### 4.3. Comprobar el frontend

Para verificar que el proyecto compila correctamente:

```bash
npm run build
```

Para ejecutar el análisis estático del código:

```bash
npm run lint
```

Ambos comandos deben terminar sin errores.

---

## 5. Ejecutar el proyecto durante el desarrollo

El backend y el frontend se ejecutan en terminales separadas.

1. Abre una terminal en la raíz del repositorio y activa el entorno virtual.
2. Inicia Django con `python backend/manage.py runserver`.
3. Abre otra terminal y entra en la carpeta `frontend/`.
4. Ejecuta `npm run dev`.
5. Accede a la dirección local de Vite desde el navegador.

El frontend y el backend todavía deben conectarse mediante Axios cuando se implementen los endpoints de la API.

---

## 6. Estructura del repositorio

```text
DomiPedidosX-Proyecto-DS1/
├── .github/
│   ├── workflows/ci.yml          # Integración continua (GitHub Actions)
│   ├── ISSUE_TEMPLATE/bug.md
│   └── PULL_REQUEST_TEMPLATE.md
├── backend/
│   ├── config/                   # Configuración del proyecto Django
│   ├── sedes/
│   ├── usuarios/
│   ├── menu/
│   ├── inventario/
│   ├── promociones/
│   ├── pedidos/
│   ├── manage.py
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
├── docs/
├── .gitignore
├── CONTRIBUTING.md
└── README.md
```

La estructura evolucionará conforme se incorporen los componentes React, los endpoints de la API y la documentación.

---

## 7. Buenas prácticas de Git

El equipo utiliza las siguientes ramas:

- `main`: versiones estables del proyecto (entregas).
- `develop`: integración del trabajo del equipo.
- `feature/HU-nn-tema`: desarrollo de una historia de usuario concreta.

`main` y `develop` están protegidas: no se sube directamente a ellas. Todo cambio entra mediante Pull Request.

### Flujo de trabajo recomendado

1. Actualizar la rama `develop`.
2. Crear una rama de trabajo desde `develop`.
3. Implementar una tarea concreta y realizar commits pequeños.
4. Subir la rama a GitHub.
5. Abrir un Pull Request hacia `develop`.
6. Esperar a que el CI termine en verde y obtener 1 aprobación de un compañero.
7. Integrar con **squash merge** y borrar la rama.

El detalle completo del flujo, los mensajes de commit y las reglas de migraciones está en [`CONTRIBUTING.md`](CONTRIBUTING.md).

### Ejemplo de flujo

```bash
git switch develop
git pull origin develop
git switch -c feature/HU-12-nombre-de-la-funcionalidad
```

Después de realizar los cambios:

```bash
git add .
git commit -m "feat(scope): describe the change"
git push -u origin feature/HU-12-nombre-de-la-funcionalidad
```

Luego, abre un Pull Request en GitHub con destino a `develop`.

### Convención de commits

Utilizamos el formato:

`<type>(<optional scope>): <description>`

Ejemplos:

```text
feat(auth): add user login endpoint
fix(products): validate product price
docs(readme): add setup instructions
test(orders): add order creation tests
refactor(users): extract validation logic
build(frontend): initialize React app with Vite
chore(git): update gitignore rules
```

Procura que los commits sean pequeños, descriptivos y relacionados con una tarea concreta.

---

## 8. Archivos que no deben subirse a GitHub

No deben versionarse:

- Entornos virtuales de Python, como `.venv/`.
- Dependencias instaladas de Node.js, como `node_modules/`.
- Archivos de compilación, como `frontend/dist/`.
- Archivos `.env` con credenciales o secretos.
- Bases de datos locales y archivos generados que no formen parte del código fuente.

Los archivos `requirements.txt`, `package.json`, `package-lock.json` y `.env.example` sí deben versionarse. El `.env.example` solo contiene nombres de variables y valores de ejemplo, nunca datos reales.

**Nunca compartas contraseñas, claves privadas ni credenciales de Supabase mediante commits o Pull Requests.**

---

## 9. Solución de problemas

### El comando `python` o `python3` no funciona

Comprueba la instalación de Python y prueba el comando disponible en tu sistema. En Windows puedes utilizar `py`.

### El comando `npm` no funciona

Instala Node.js y npm, abre una nueva terminal y verifica las versiones con:

```bash
node --version
npm --version
```

### No se encuentra una dependencia de Python

Activa el entorno virtual de `backend/` e instala las dependencias con:

```bash
python -m pip install -r backend/requirements.txt
```

### El frontend no encuentra sus dependencias

Entra en `frontend/` y ejecuta:

```bash
npm ci
```

### `KeyError` al iniciar Django (por ejemplo `DJANGO_SECRET_KEY`)

Falta una variable de entorno. Comprueba que existe `backend/.env` (copiado de `backend/.env.example`) y que tiene todas las variables completas.

### Error de conexión con la base de datos

Verifica que PostgreSQL está en ejecución y que los datos de `backend/.env` coinciden con el rol y la base que creaste (sección 3.4).

### `pytest` falla con "permission denied to create database"

El rol de PostgreSQL necesita el permiso `CREATEDB`:

```bash
sudo -u postgres psql -c "ALTER ROLE domipedidosx CREATEDB;"
```

Usa el nombre de tu rol.

### El puerto ya está ocupado

Revisa si existe otro proceso ejecutando el backend o el frontend. Si es necesario, detén el proceso anterior antes de iniciar otro.

### No puedo activar el entorno virtual en PowerShell

Si la política de ejecución de PowerShell impide activar el entorno, puedes utilizar CMD o ejecutar directamente el intérprete del entorno virtual:

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py runserver
```

---

## 10. Próximos pasos

- Implementar los endpoints de la API por historia de usuario.
- Conectar React con Django mediante Axios.
- Ampliar las pruebas conforme avance cada sprint.
- Configurar el despliegue (Supabase, Vercel y el servicio de hosting del backend).

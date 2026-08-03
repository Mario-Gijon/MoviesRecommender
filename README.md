# Movies Recommender

Explainable movie recommender web app for a public science outreach event. The project is designed to teach recommendation systems in a white-box way, starting with simple deterministic placeholders before real catalog and recommendation logic is added.

## Local development

### Frontend

```bash
cd Frontend
bun install
bun dev
```

### Backend

```bash
cd Backend
uvicorn app.main:app --reload --port 8014
```

## Docker and deployment

Production Compose uses image references and keeps all generated runtime data on the
host through `DATA_DIR` (default `./Backend/data`). This includes both the shared
`offline_dataset/` and recommender-specific `recommender_models/` directories, so
they survive `stop`, `down`, image pulls, and restarts.

Docker users configure `DATA_DIR` in `.env`; the interactive manager supplies the
appropriate Compose environment internally. `MOVIES_RECOMMENDER_DATA_DIR=/app/data`
is used inside backend containers. It is only relevant when running Python directly
outside Docker, where its default remains `Backend/data`.

The backend is available by itself on `${BACKEND_BIND_HOST}:${BACKEND_PORT}`. The
optional production frontend is served on `${FRONTEND_BIND_HOST}:${FRONTEND_PORT}`
and proxies `/api/`, `/offline/`, and `/audit/` to the backend internally. Defaults
bind to `127.0.0.1`; set either bind host to `0.0.0.0` only when LAN/server access is
intended. Image names, ports, bind hosts, and `DATA_DIR` are configurable in `.env`.

El gestor selecciona Desarrollo con código montado o Producción con imágenes
publicadas. El Frontend de Desarrollo mantiene `VITE_API_URL=http://localhost:8014`;
el Frontend de Producción usa rutas relativas `/api` mediante Nginx.

## Dataset generation

The opt-in `dataset` service generates `offline_dataset/` from MovieLens 32M and
TMDB metadata. It reuses valid raw files and cached work where possible, but
regenerates the selected candidate, enrichment, catalogue, ratings, export, poster,
and audit outputs. It never rebuilds `recommender_models/`.

During this transition phase, choose Dataset from `python manage.py` to open the
existing interactive wizard.

The `recommended` profile creates the broad 15,000-item configuration; choose
`custom` in the wizard for individual limits, years, language, stages, poster and
audit options. Deterministic installation-style use is available with, for example:

```bash
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN='...' \
  .venv/bin/python -m pipelines.dataset_generation.cli \
  --non-interactive --yes --source download --preset recommended --audit
```

The imported raw CSVs are written under persistent `DATA_DIR`; the original host ZIP
is not modified. Enrichment requires `MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN`; set it
in the environment (or enter it through the existing interactive prompt). Dataset
source selection, resume behavior, poster download, audit generation and cleanup are
se rediseñarán en la siguiente fase.

## Gestor interactivo

Solo se necesitan Python, Docker y Docker Compose. Configura un `DATA_DIR` con
permisos de escritura y ejecuta el gestor con:

```bash
python manage.py
```

El gestor guía las operaciones de la aplicación sin exigir comandos de Compose,
perfiles, flags ni selección de algoritmos. Desarrollo usa el código local con reload
y HMR; Producción usa las imágenes publicadas. La reconstrucción de modelos usa siempre
las variantes activas declaradas en `.env` y mantiene `DATA_DIR` persistente.

Dataset abre temporalmente su flujo interactivo existente mientras se prepara su
gestión específica. Configuración se implementará en la siguiente fase.

### Paquete de despliegue autónomo

Quien mantenga el proyecto puede generar el paquete de producción con:

```bash
python scripts/build_deployment_package.py
```

Se distribuyen inicialmente solo `manage.pyz` y `compose.yaml` desde
`dist/MoviesRecommender/`. En el primer arranque, `python manage.pyz` crea mediante
un asistente `.env` y el directorio persistente `data/`; por tanto la instalación
contiene después `manage.pyz`, `compose.yaml`, `.env` y `data/`. El código de la
aplicación procede de las imágenes publicadas en Docker Hub. Ni el dataset ni los
modelos se incluyen en el paquete.

## Reconstrucción de artefactos de recomendación

Generar `offline_dataset/` no reconstruye `recommender_models/`. Reconstruir
`recommender_models/` no regenera `offline_dataset/`. El gestor reconstruye los
artefactos actuales manteniendo esa separación.

```bash
cd Backend
.venv/bin/python -m pipelines.recommender_build.cli --yes
.venv/bin/python -m pipelines.recommender_build.cli --algorithm item_knn --algorithm biased --yes
.venv/bin/python -m pipelines.recommender_build.cli --algorithm item_knn --clean --yes
```

El proceso de mantenimiento construye cada objetivo seleccionado bajo
`DATA_DIR/tmp`, lo valida, puede retirar artefactos no necesarios para ejecución con
`--clean` y después instala ese objetivo bajo `recommender_models/`.
Para despliegues Compose, copia el `.env.example` raíz a `.env`; para ejecutar el
Backend directamente con Python, copia `Backend/.env.example` a `Backend/.env`. Las
solicitudes de la API seleccionan algoritmos, nunca variantes. Cada reemplazo usa una
copia de seguridad hermana en el mismo sistema de archivos; si la recuperación falla,
el error identifica esa copia para su revisión manual. Un fallo posterior no deshace
los objetivos ya instalados.
Las variantes son internas al despliegue. Item KNN usa por defecto
`top_k_100_min_support_25`; `top_k_50_min_support_25` también es compatible. El perfil
de despliegue BMF es `factors_128_epochs_100_lr_0_005_reg_0_02`. La API y el
mantenimiento comparten las variantes activas de `.env`; el gestor usa solo perfiles
compatibles. El Dataset offline no se regenera durante esta operación ni se crean
auditorías.

El gestor interactivo ejecuta este proceso con el entorno y el perfil adecuados; no es
necesario invocar Docker Compose directamente.

## Alcance actual

- Datos persistentes de ejecución configurables y base de despliegue Docker.
- Sin autenticación ni cuentas de usuario.
- Sin paquete de instalación externo ni flujo de publicación en Docker Hub.

## Fases posteriores

- Paquete de instalación externo y flujo de publicación en Docker Hub.

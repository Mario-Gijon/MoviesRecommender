# Movies Recommender

Aplicación web de recomendación de películas orientada a divulgación científica y demostraciones públicas. El proyecto permite generar un dataset offline, construir varios modelos de recomendación, ejecutar la API y utilizar una interfaz web mediante Docker.

## Funcionalidades principales

- Generación de un dataset offline a partir de MovieLens 32M.
- Enriquecimiento de películas mediante TMDB.
- Descarga y almacenamiento local de pósteres.
- Catálogo público configurable.
- Modelos de recomendación basados en contenido y filtrado colaborativo.
- Backend HTTP para integraciones externas, incluida una interfaz desarrollada en Unity.
- Frontend web para valorar películas y consultar recomendaciones.
- Gestor interactivo para controlar la instalación sin ejecutar manualmente comandos de Docker Compose.

## Arquitectura

El proyecto está dividido en cuatro partes principales:

```text
MoviesRecommender/
├── Backend/
├── Frontend/
├── manager/
├── Docs/
├── compose.yaml
├── compose.dev.yaml
└── manage.py
```

### Backend

API desarrollada con Python y FastAPI.

Se encarga de:

- Servir el catálogo de películas.
- Recibir valoraciones del usuario.
- Ejecutar los algoritmos de recomendación.
- Exponer los resultados mediante HTTP.
- Servir los datos y pósteres del dataset offline.

### Frontend

Aplicación web desarrollada con React y Vite.

Permite:

- Explorar el catálogo.
- Valorar películas.
- Seleccionar estrategias y algoritmos.
- Generar y consultar recomendaciones.
- Mantener temporalmente el estado de la sesión en el navegador.

### Dataset offline

El dataset se genera a partir de MovieLens 32M y se enriquece con información de TMDB.

Los datos persistentes se guardan en el directorio configurado mediante `DATA_DIR`. Por defecto:

```text
./data
```

Dentro de este directorio se almacenan:

```text
data/
├── offline_dataset/
├── recommender_models/
└── logs/
```

### Modelos de recomendación

La aplicación incluye los siguientes algoritmos:

- TF-IDF.
- Popularidad.
- Item KNN.
- User KNN.
- Biased Matrix Factorization.

La generación del dataset y la construcción de los modelos son procesos separados. Después de generar o modificar el dataset, los modelos deben reconstruirse para asegurar su compatibilidad.

## Gestor interactivo

El gestor permite configurar y controlar la instalación desde un menú interactivo.

Desde el repositorio:

```bash
python manage.py
```

Desde el paquete autónomo:

```bash
python manage.pyz
```

En Linux también puede utilizarse:

```bash
python3 manage.pyz
```

El gestor permite:

- Configurar el directorio de datos, los puertos y el acceso de red.
- Guardar el token bearer de TMDB.
- Generar, reconstruir y reanudar el dataset offline.
- Validar y consultar el dataset.
- Construir y validar los modelos.
- Iniciar, detener, reiniciar y actualizar el Backend.
- Iniciar, detener, reiniciar y actualizar el Frontend.
- Consultar el estado y los registros de los servicios.

## Paquete de despliegue autónomo

El paquete de producción se genera con:

```bash
python scripts/build_deployment_package.py
```

El resultado se crea en:

```text
dist/MoviesRecommender/
├── manage.pyz
└── compose.yaml
```

Este paquete no incluye el dataset, los modelos ni el código fuente. El gestor descarga las imágenes publicadas en Docker Hub y crea durante la primera ejecución:

```text
.env
data/
```

## Imágenes Docker

La instalación de producción utiliza:

```text
mariogijon/movies-recommender-api:latest
mariogijon/movies-recommender-dataset:latest
mariogijon/movies-recommender-frontend:latest
```

El archivo `compose.yaml` utiliza estas imágenes para ejecutar el Backend, generar el dataset, construir los modelos y servir el Frontend.

## Documentación

La documentación de uso se encuentra en `Docs/`:

- [`Docs/guia-cli-es.md`](Docs/guia-cli-es.md): explicación de las opciones disponibles en el gestor.
- [`Docs/configuracion-recomendada-es.md`](Docs/configuracion-recomendada-es.md): recorrido recomendado para generar el dataset, construir los modelos e iniciar el Backend.

## Desarrollo local

### Backend

```bash
cd Backend
python -m uvicorn app.main:app --reload --port 8014
```

### Frontend

```bash
cd Frontend
bun install
bun dev
```

### Docker Compose de desarrollo

```bash
docker compose -f compose.dev.yaml up
```

## Despliegue con Docker Compose

La configuración de producción se encuentra en `compose.yaml`.

Los puertos, el directorio de datos y el acceso de red se configuran mediante `.env`.

Variables principales:

```text
COMPOSE_PROJECT_NAME
DATA_DIR
BACKEND_PORT
FRONTEND_PORT
BACKEND_BIND_HOST
FRONTEND_BIND_HOST
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN
```

Los valores predeterminados del paquete autónomo se solicitan durante la primera ejecución del gestor.

## Acceso al Backend

Desde el mismo equipo:

```text
http://localhost:<puerto-backend>
```

Desde otro equipo de la red local:

```text
http://<IP-del-equipo>:<puerto-backend>
```

La ruta principal para solicitar recomendaciones es:

```text
POST /recommendations
```

## Estado del proyecto

El proyecto dispone actualmente de:

- Backend funcional.
- Frontend funcional.
- Generación offline del dataset.
- Enriquecimiento con TMDB.
- Descarga de pósteres.
- Cinco algoritmos de recomendación.
- Gestión de compatibilidad entre dataset y modelos.
- Despliegue mediante Docker.
- Paquete autónomo basado en `manage.pyz`.
- Documentación de instalación y uso.

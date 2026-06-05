# 01 — Mapa general del backend

## Objetivo del backend

El backend ofrece una API local para una demo de recomendación de películas. Sus responsabilidades principales son:

1. Servir el catálogo público de películas.
2. Servir imágenes locales de pósters.
3. Recibir valoraciones temporales del usuario.
4. Devolver recomendaciones.
5. Mantener una pipeline offline para reconstruir el dataset.

---

## Arquitectura actual

El backend se puede entender en cuatro bloques:

```text
1. API FastAPI
2. Repositorio runtime del catálogo offline
3. Scripts de pipeline de datos
4. Dataset offline generado
```

---

## 1. API FastAPI

Archivo principal:

```text
Backend/app/main.py
```

Responsabilidades:

- crea la aplicación FastAPI;
- configura CORS;
- incluye rutas de health, catálogo y recomendaciones;
- monta la carpeta de pósters locales en `/offline/posters`.

Conceptualmente:

```text
/offline/posters/{movieId}.jpg
    Sirve pósters locales desde app/data/offline_dataset/images/posters.

/movies/public-catalog
    Devuelve películas públicas paginadas.

/movies/featured
    Devuelve películas destacadas/públicas.

/catalog/status
    Devuelve estado del catálogo.

/recommendations
    Devuelve recomendaciones. Ahora mismo todavía es placeholder.
```

---

## 2. Repositorio runtime del catálogo

Archivo principal:

```text
Backend/app/infrastructure/catalog/offline_catalog_repository.py
```

Responsabilidades:

- leer `offline_dataset/csv/public_movies.csv`;
- cargar las películas públicas en memoria;
- conservar el orden del CSV;
- filtrar por búsqueda y género;
- devolver objetos compatibles con los schemas de API;
- construir `posterUrl` local si existe el póster;
- no exponer películas de soporte colaborativo ni descartadas.

Importante:

```text
Runtime solo lee public_movies.csv para catálogo visible.
```

`collaborative_support_movies.csv` no se expone a frontend. Se usará más adelante para el modelo colaborativo.

---

## 3. Rutas de catálogo

Archivo:

```text
Backend/app/api/routes/catalog_routes.py
```

Endpoints:

```text
GET /catalog/status
GET /movies/featured
GET /movies/public-catalog
```

La ruta de catálogo público permite:

```text
page
pageSize
search
genre
```

El backend conserva el orden del CSV público y aplica filtros en memoria.

---

## 4. Rutas de recomendación

Archivo:

```text
Backend/app/api/routes/recommendation_routes.py
```

Endpoint:

```text
POST /recommendations
```

Ahora llama a:

```text
build_placeholder_response(...)
```

en:

```text
Backend/app/domain/recommendations/recommendation_strategy.py
```

Todavía no hay recomendador real. Lo que hay es una respuesta placeholder que usa el catálogo público para generar resultados demostrativos.

---

## 5. Schemas de dominio

Películas:

```text
Backend/app/domain/movies/movie_schemas.py
```

Recomendaciones:

```text
Backend/app/domain/recommendations/recommendation_schemas.py
```

Estos schemas definen qué forma tienen las respuestas API.

---

## 6. Dataset y rutas de datos

Archivo central de rutas:

```text
Backend/app/infrastructure/datasets/movielens_paths.py
```

Define:

```text
DATA_DIR
RAW_MOVIELENS_DIR
PIPELINE_CACHE_DIR
ML_32M_PIPELINE_CACHE_DIR
OFFLINE_DATASET_DIR
OFFLINE_DATASET_CSV_DIR
OFFLINE_DATASET_POSTERS_DIR
```

Esto evita rutas hardcodeadas dispersas.

---

## Qué se eliminó

Ya no existe runtime SQLite:

```text
catalog_models.py
catalog_mapper.py
catalog_repository.py antiguo
database/session.py
seed_demo_catalog_from_movielens_32m.py
seed_placeholder_catalog.py
placeholder_catalog.py
```

También se quitó SQLAlchemy de requirements porque no hay código runtime que lo use.

---

## Regla importante

La fuente runtime actual es:

```text
offline_dataset/
```

No es:

```text
raw/
pipeline_cache/
TMDB
SQLite
```


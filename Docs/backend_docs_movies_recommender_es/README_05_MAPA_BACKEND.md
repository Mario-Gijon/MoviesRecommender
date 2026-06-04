# Backend — Mapa de ficheros y responsabilidades

Este documento explica qué hace cada parte importante del backend.

---

## 1. Entrada de la app

## `Backend/app/main.py`

Crea la aplicación FastAPI.

Responsabilidades:

- Crear `FastAPI(...)`.
- Configurar CORS.
- Registrar routers:
  - health
  - catalog
  - recommendations

No debería contener lógica de negocio.

---

# 2. Configuración

## `Backend/app/core/config.py`

Centraliza configuración.

Responsabilidades:

- Nombre de app.
- Versión.
- CORS.
- URL de base de datos.
- Token TMDB.
- Carga de `.env`.

Lo usan tanto scripts como runtime.

---

# 3. Rutas API

## `Backend/app/api/routes/health_routes.py`

Endpoints de salud.

Sirven para comprobar que la API está viva.

---

## `Backend/app/api/routes/catalog_routes.py`

Endpoints del catálogo.

Define:

```text
GET /catalog/status
GET /movies/featured
GET /movies/public-catalog
```

### `/catalog/status`

Devuelve estado del catálogo.

### `/movies/featured`

Endpoint compatible/antiguo. Devuelve películas públicas.

### `/movies/public-catalog`

Endpoint principal del frontend.

Permite:

- Paginación.
- Búsqueda.
- Filtro por género.

Parámetros:

```text
page
pageSize
search
genre
```

---

## `Backend/app/api/routes/recommendation_routes.py`

Endpoint de recomendaciones.

Define:

```text
POST /recommendations
```

Ahora mismo llama al recomendador placeholder.

---

# 4. Dominio de películas

## `Backend/app/domain/movies/movie_schemas.py`

Define modelos Pydantic de películas.

Modelos principales:

```text
Movie
MovieCoverage
CatalogStatus
PaginatedMovieCatalogResponse
```

### `Movie`

Lo que recibe el frontend.

Incluye:

- IDs.
- Títulos.
- `displayTitle`.
- `displayOverview`.
- Póster.
- Géneros.
- `displayGenres`.
- Tags.
- Coverage.

### `MovieCoverage`

Indica cobertura de contenido y colaborativa.

---

# 5. Dominio de recomendaciones

## `Backend/app/domain/recommendations/recommendation_schemas.py`

Define contratos de recomendación.

Incluye:

- Request.
- Rating de usuario.
- Respuesta.
- Item recomendado.
- Señales de explicación.
- Perfil temporal.

---

## `Backend/app/domain/recommendations/recommendation_strategy.py`

Contiene la recomendación actual.

Estado:

- Placeholder.
- Determinista.
- Usa géneros/tags de películas valoradas.
- Devuelve explicaciones simuladas.

Futuro:

- Dividir o sustituir por recomendador basado en contenido.
- Añadir colaborativo.
- Añadir híbrido.
- Añadir explicaciones reales.

---

# 6. Infraestructura de catálogo

## `Backend/app/infrastructure/catalog/catalog_models.py`

Define tablas SQLAlchemy.

Tablas:

```text
movies
movie_genres
movie_tags
movie_coverage_notes
```

### `MovieRecord`

Tabla principal de películas.

Guarda:

- IDs.
- Títulos canónicos y display.
- Overview canónico y display.
- Año.
- Póster/backdrop.
- Flags de catálogo.
- Scores.
- Cobertura.
- Métricas TMDB/MovieLens.

### `MovieGenreRecord`

Géneros.

Guarda:

- `name`: canónico.
- `display_name`: español/display.

### `MovieTagRecord`

Tags y keywords normalizados.

### `MovieCoverageNoteRecord`

Notas de cobertura.

---

## `Backend/app/infrastructure/catalog/catalog_mapper.py`

Convierte registros SQLite a dict API.

Responsabilidades:

- Devolver campos canónicos.
- Devolver campos display con fallback.
- Convertir relaciones de géneros/tags/notas.

Ejemplo conceptual:

```text
displayTitle = display_title or title
displayOverview = display_overview or overview
displayGenres = display_name or name
```

---

## `Backend/app/infrastructure/catalog/catalog_repository.py`

Capa de acceso a SQLite.

Responsabilidades:

- `get_status()`
- `get_featured_movies()`
- `get_recommendation_candidates()`
- `get_public_catalog_page()`

También construye queries de búsqueda y filtro.

La búsqueda debería contemplar:

- `title`
- `original_title`
- `display_title`

El filtro de género debería contemplar:

- `name`
- `display_name`

---

## `Backend/app/infrastructure/catalog/placeholder_catalog.py`

Datos hardcodeados antiguos.

Estado:

- Legacy.
- Solo útil para pruebas sin dataset.

---

# 7. Base de datos

## `Backend/app/infrastructure/database/session.py`

Configura SQLAlchemy.

Responsabilidades:

- Engine.
- SessionLocal.
- Base.
- Conexión SQLite.

---

# 8. Rutas de datasets

## `Backend/app/infrastructure/datasets/movielens_paths.py`

Centraliza rutas de datos.

Responsabilidades:

- Rutas raw.
- Rutas processed.
- Rutas de CSV/JSON generados.

Si se añade un nuevo artefacto, normalmente se añade aquí una constante.

---

# 9. Scripts

Carpeta:

```text
Backend/app/scripts/
```

Scripts principales:

```text
download_movielens_32m.py
inspect_movielens_32m.py
build_movielens_32m_candidates.py
enrich_movielens_32m_with_tmdb.py
inspect_tmdb_enriched_movielens_32m.py
build_demo_catalog_from_movielens_32m.py
export_demo_catalog_32m_review_files.py
build_demo_ratings_from_movielens_32m.py
seed_demo_catalog_from_movielens_32m.py
```

Script legacy:

```text
seed_placeholder_catalog.py
```

---

# 10. Datos locales

## `Backend/app/data/raw/`

Datos descargados originales.

No se suben a git.

---

## `Backend/app/data/processed/`

Datos generados por scripts.

No se suben a git.

---

## `Backend/app/data/catalog.sqlite`

Base de datos runtime.

La crea:

```bash
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

La usa la API.

---

# 11. Flujo runtime de catálogo

```text
Frontend
   ↓
GET /movies/public-catalog
   ↓
catalog_routes.py
   ↓
catalog_repository.py
   ↓
catalog.sqlite
   ↓
catalog_mapper.py
   ↓
Movie schema
   ↓
JSON al frontend
```

---

# 12. Flujo runtime de recomendaciones

```text
Frontend
   ↓
POST /recommendations
   ↓
recommendation_routes.py
   ↓
recommendation_strategy.py
   ↓
catalog_repository.py
   ↓
catalog.sqlite
   ↓
RecommendationResponse
```

Actualmente la estrategia es placeholder.

---

# 13. Cosas candidatas a limpiar

- Marcar `seed_placeholder_catalog.py` como legacy o eliminarlo si ya no se necesita.
- Marcar `placeholder_catalog.py` como legacy o eliminarlo si ya no se necesita.
- Revisar textos de README que hablen de placeholder como estado actual.
- Revisar mensajes de error que recomienden `seed_placeholder_catalog` y cambiarlos por `seed_demo_catalog_from_movielens_32m`.

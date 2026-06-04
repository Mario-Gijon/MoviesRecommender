# Backend — Pipeline y scripts

Este documento explica qué hace cada script del backend, qué lee y qué genera.

## 1. Idea general

La app no usa directamente MovieLens 32M en runtime. Primero se procesan los datos offline y después se cargan en SQLite.

```text
raw MovieLens
   ↓
inspección
   ↓
candidatos
   ↓
enriquecimiento TMDB
   ↓
catálogo demo
   ↓
CSV de revisión
   ↓
ratings filtrados
   ↓
SQLite
   ↓
API FastAPI
```

---

## 2. `download_movielens_32m.py`

### Qué hace

Descarga y descomprime MovieLens 32M.

### Escribe

```text
Backend/app/data/raw/movielens/ml-32m.zip
Backend/app/data/raw/movielens/ml-32m/ml-32m/movies.csv
Backend/app/data/raw/movielens/ml-32m/ml-32m/ratings.csv
Backend/app/data/raw/movielens/ml-32m/ml-32m/tags.csv
Backend/app/data/raw/movielens/ml-32m/ml-32m/links.csv
```

### Cuándo se usa

Al principio, o si borras los datos raw.

### Comando

```bash
python -m app.scripts.download_movielens_32m
```

---

## 3. `inspect_movielens_32m.py`

### Qué hace

Inspecciona el dataset raw.

### Lee

```text
movies.csv
ratings.csv
tags.csv
links.csv
```

### Escribe

```text
ml_32m_summary.json
```

### Para qué sirve

Para conocer el dataset antes de filtrar:

- Total de películas.
- Total de ratings.
- Total de tags.
- Usuarios únicos.
- Cobertura de `tmdbId` e `imdbId`.
- Rango de años.
- Top películas por número de ratings.

### Comando

```bash
python -m app.scripts.inspect_movielens_32m
```

---

## 4. `build_movielens_32m_candidates.py`

### Qué hace

Crea una lista reducida de películas candidatas desde MovieLens.

### Por qué existe

MovieLens tiene muchísimas películas. No queremos llamar a TMDB para todas. Este script selecciona una lista moderna y con suficientes datos.

### Lee

```text
movies.csv
ratings.csv
tags.csv
links.csv
```

### Escribe

```text
ml_32m_candidates.json
```

### Campos importantes que genera

- `movieId`
- `title`
- `cleanTitle`
- `year`
- `genres`
- `ratingCount`
- `averageRating`
- `tmdbId`
- `imdbId`
- `userTags`
- `candidateScore`
- `dataReliabilityScore`
- `recencyScore`

### Comando

```bash
python -m app.scripts.build_movielens_32m_candidates
```

---

## 5. `enrich_movielens_32m_with_tmdb.py`

### Qué hace

Enriquece las candidatas con TMDB.

### Lee

```text
ml_32m_candidates.json
```

### Escribe

```text
ml_32m_tmdb_enriched.json
```

### Requiere

```text
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN
```

### Qué añade

- Póster.
- Backdrop.
- Overview.
- Géneros.
- Keywords.
- Reparto principal.
- Directores.
- Certificaciones.
- Popularidad.
- Votos.
- Runtime.
- Idioma original.
- Campos display en español.

### Campos canónicos vs display

Canónicos/internos:

```text
title
overview
genres
keywords
```

Display para UI española:

```text
displayTitle
displayOverview
displayGenres
```

### Comandos

Prueba limitada:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --limit 100
```

Continuar/backfill:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --resume
```

Forzar reconstrucción:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --force --sleep 0.35
```

---

## 6. `inspect_tmdb_enriched_movielens_32m.py`

### Qué hace

Inspecciona el JSON enriquecido con TMDB.

### Lee

```text
ml_32m_tmdb_enriched.json
```

### Escribe

```text
ml_32m_tmdb_inspection.json
```

### Para qué sirve

Para revisar:

- Cobertura de pósters.
- Cobertura de keywords.
- Cobertura de certificaciones ES/US.
- Distribución por géneros.
- Distribución por décadas/años.
- Family-friendly candidates.
- Teen candidates.
- Adult/sensitive candidates.
- Unknown suitability.

### Comando

```bash
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
```

---

## 7. `build_demo_catalog_from_movielens_32m.py`

### Qué hace

Construye el catálogo demo real.

### Lee

```text
ml_32m_tmdb_enriched.json
```

### Escribe

```text
ml_32m_demo_catalog.json
```

### Estructura del JSON

```json
{
  "source": {},
  "summary": {},
  "publicCatalog": [],
  "collaborativeCore": [],
  "excludedOrSensitive": []
}
```

### `publicCatalog`

Películas visibles, valorables y recomendables.

### `collaborativeCore`

Películas internas con datos colaborativos suficientes.

### `excludedOrSensitive`

Películas excluidas del catálogo público.

### Qué calcula

- `demoSuitability`
- `suitabilityReasons`
- `publicExclusionReasons`
- `standDisplayScore`
- `standDisplayReasons`
- `catalogRoles`

### Comandos

Normal:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
```

Solo family-friendly:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m --family-only
```

Limitar catálogo público:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m --public-limit 200
```

---

## 8. `export_demo_catalog_32m_review_files.py`

### Qué hace

Exporta el catálogo demo a CSVs de revisión.

### Lee

```text
ml_32m_demo_catalog.json
```

### Escribe

```text
ml_32m_demo_catalog_public.csv
ml_32m_demo_catalog_collaborative_core.csv
ml_32m_demo_catalog_excluded.csv
```

### Para qué sirve

Para abrir en LibreOffice/Excel y revisar manualmente.

### Comando

```bash
python -m app.scripts.export_demo_catalog_32m_review_files
```

---

## 9. `build_demo_ratings_from_movielens_32m.py`

### Qué hace

Filtra el `ratings.csv` raw y se queda con los ratings de películas de `collaborativeCore`.

### Lee

```text
ratings.csv
ml_32m_demo_catalog.json
```

### Escribe

```text
ml_32m_demo_ratings.csv
ml_32m_demo_ratings_by_movie.csv
ml_32m_demo_ratings_summary.json
```

### Para qué sirve

Preparar la futura recomendación colaborativa.

### Salidas

#### `ml_32m_demo_ratings.csv`

Ratings filtrados. Puede ser grande. No es para revisión manual.

Columnas:

```text
userId
movieId
rating
timestamp
```

#### `ml_32m_demo_ratings_by_movie.csv`

Resumen por película. Sí es para revisar.

#### `ml_32m_demo_ratings_summary.json`

Resumen global.

### Comando

```bash
python -m app.scripts.build_demo_ratings_from_movielens_32m
```

---

## 10. `seed_demo_catalog_from_movielens_32m.py`

### Qué hace

Carga el catálogo procesado en SQLite.

### Lee

```text
ml_32m_demo_catalog.json
```

### Escribe

```text
Backend/app/data/catalog.sqlite
```

### Qué guarda

- Películas públicas.
- Películas collaborative core.
- Títulos canónicos y display.
- Overviews canónicos y display.
- Pósters/backdrops.
- Géneros canónicos y display.
- Tags.
- Scores.
- Coverage.

### Comando

```bash
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

---

## 11. `seed_placeholder_catalog.py`

### Qué hace

Carga datos hardcodeados antiguos desde `placeholder_catalog.py`.

### Estado

Legacy/desarrollo inicial. No es la pipeline activa si usamos MovieLens 32M.

### Recomendación

No usar salvo que quieras una demo mínima sin dataset.

---

## 12. Orden recomendado

Pipeline completa:

```bash
python -m app.scripts.download_movielens_32m
python -m app.scripts.inspect_movielens_32m
python -m app.scripts.build_movielens_32m_candidates
python -m app.scripts.enrich_movielens_32m_with_tmdb --resume
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.export_demo_catalog_32m_review_files
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

Pipeline habitual si ya está descargado/enriquecido:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.export_demo_catalog_32m_review_files
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

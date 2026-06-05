# 03 — Pipeline de datos y scripts

Este documento explica qué hace cada script y cómo se conectan.

---

## Visión general

La pipeline completa es:

```text
MovieLens raw
    ↓
candidatas MovieLens
    ↓
enriquecimiento TMDB
    ↓
catálogo particionado
    ↓
ratings filtrados
    ↓
offline_dataset CSV + posters
```

---

## Orden completo de reconstrucción manteniendo `raw/`

Si ya tienes MovieLens descargado en `raw/`, puedes reconstruir todo con:

```bash
python -m app.scripts.inspect_movielens_32m
python -m app.scripts.build_movielens_32m_candidates
python -m app.scripts.enrich_movielens_32m_with_tmdb
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.export_offline_dataset_from_movielens_32m
python -m app.scripts.download_offline_movie_posters
```

Si no tienes MovieLens descargado, antes:

```bash
python -m app.scripts.download_movielens_32m
```

---

# Scripts

## 1. `download_movielens_32m.py`

Descarga y extrae MovieLens 32M.

Genera:

```text
app/data/raw/movielens/ml-32m.zip
app/data/raw/movielens/ml-32m/ml-32m/
```

No se ejecuta si ya tienes `raw/`.

---

## 2. `inspect_movielens_32m.py`

Inspecciona el dataset raw.

Genera:

```text
pipeline_cache/movielens_32m/source_dataset_summary.json
```

Sirve para diagnóstico.

No es estrictamente necesario para runtime, pero es útil para saber qué contiene MovieLens.

---

## 3. `build_movielens_32m_candidates.py`

Selecciona candidatas desde MovieLens.

Lee:

```text
movies.csv
ratings.csv
tags.csv
links.csv
```

Genera:

```text
pipeline_cache/movielens_32m/candidate_movies.json
```

Parámetros importantes:

```text
--limit              default 2000
--min-ratings        default 100
--min-year           default 2000
--max-year
--max-tags-per-movie default 10
```

Qué hace:

1. Calcula `ratingCount` y `averageRating` por película.
2. Filtra por mínimo de ratings.
3. Filtra por año mínimo.
4. Añade `tmdbId` e `imdbId`.
5. Añade tags de usuarios de MovieLens.
6. Calcula:
   - `dataReliabilityScore`
   - `recencyScore`
   - `candidateScore`
7. Ordena por score y se queda con el límite.

---

## 4. `enrich_movielens_32m_with_tmdb.py`

Enriquece las candidatas con TMDB.

Lee:

```text
candidate_movies.json
```

Genera:

```text
tmdb_enriched_movies.json
```

Necesita token:

```text
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN
```

Qué pide a TMDB:

- detalles de película;
- keywords;
- créditos;
- release_dates/certificaciones;
- datos display en español con `display-language`, default `es-ES`.

Guarda:

```text
posterPath
overview
displayTitle
displayOverview
genres
displayGenres
keywords
topCast
directors
certifications
runtime
originalLanguage
popularity
voteAverage
voteCount
```

Opciones:

```text
--limit
--force
--resume
--sleep
--display-language
```

Uso recomendado al reconstruir completamente:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --force
```

Uso recomendado para continuar un enriquecimiento a medias:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --resume
```

---

## 5. `inspect_tmdb_enriched_movielens_32m.py`

Inspecciona el enriquecido TMDB.

Genera:

```text
tmdb_enrichment_inspection.json
```

Sirve para ver:

```text
cobertura de póster
cobertura de keywords
cobertura de certificaciones
distribución por suitability
top por rating/popularidad
```

No es runtime.

---

## 6. `build_demo_catalog_from_movielens_32m.py`

Construye el catálogo particionado.

Lee:

```text
tmdb_enriched_movies.json
```

Genera:

```text
partitioned_demo_catalog.json
```

Produce tres listas:

```text
publicCatalog
collaborativeCore
excludedOrSensitive
```

Parámetros:

```text
--public-limit                 default None
--collaborative-core-limit     default 2000
--min-ratings                  default 100
--public-min-year              default 2000
--collaborative-min-year       default 2000
--family-only
```

Este script contiene la heurística principal de:

- clasificación de suitability;
- cálculo de `standDisplayScore`;
- filtro público;
- filtro colaborativo;
- orden de películas públicas.

---

## 7. `build_demo_ratings_from_movielens_32m.py`

Filtra los ratings de MovieLens para el núcleo colaborativo.

Lee:

```text
raw ratings.csv
partitioned_demo_catalog.json
```

Genera:

```text
filtered_collaborative_ratings.csv
filtered_collaborative_ratings_by_movie.csv
filtered_collaborative_ratings_summary.json
```

Qué hace:

- recorre el `ratings.csv` gigante en streaming;
- solo escribe ratings de películas del core colaborativo;
- calcula resumen por película.

Esto evita trabajar directamente con los 32 millones de ratings.

---

## 8. `export_offline_dataset_from_movielens_32m.py`

Exporta el dataset final portable.

Lee:

```text
partitioned_demo_catalog.json
filtered_collaborative_ratings.csv
filtered_collaborative_ratings_by_movie.csv
```

Genera:

```text
offline_dataset/manifest.json
offline_dataset/csv/public_movies.csv
offline_dataset/csv/collaborative_support_movies.csv
offline_dataset/csv/excluded_movies.csv
offline_dataset/csv/movie_ratings_summary.csv
offline_dataset/csv/collaborative_ratings.csv
```

Reglas:

```text
public_movies.csv = publicCatalog
collaborative_support_movies.csv = collaborativeCore - public, quitando solo inválidas técnicas
excluded_movies.csv = lo que no es public ni support
collaborative_ratings.csv = ratings de public + support
```

---

## 9. `download_offline_movie_posters.py`

Descarga pósters locales para las películas públicas.

Lee:

```text
offline_dataset/csv/public_movies.csv
```

Descarga desde:

```text
https://image.tmdb.org/t/p/w500{posterPath}
```

Guarda:

```text
offline_dataset/images/posters/{movieId}.jpg
```

No descarga backdrops.

Opciones:

```text
--force
--limit
--sleep
```

Uso normal:

```bash
python -m app.scripts.download_offline_movie_posters
```

---

## Scripts eliminados

Ya no existen:

```text
seed_placeholder_catalog.py
seed_demo_catalog_from_movielens_32m.py
export_demo_catalog_32m_review_files.py
```

Motivo:

- SQLite ya no es runtime.
- Los CSV finales viven en `offline_dataset`.
- El export antiguo de CSV review quedó sustituido por el export offline final.


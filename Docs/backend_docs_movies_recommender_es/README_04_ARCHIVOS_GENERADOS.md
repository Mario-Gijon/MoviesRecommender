# Backend — Archivos generados CSV/JSON

Este documento explica qué archivos de datos se generan y cuáles conviene mirar.

---

## 1. Importante

Los datos en estas carpetas son locales:

```text
Backend/app/data/raw/
Backend/app/data/processed/
```

No deberían subirse a git.

---

# 2. Datos raw

## `ml-32m.zip`

Dataset descargado.

Ruta:

```text
Backend/app/data/raw/movielens/ml-32m.zip
```

No se usa en runtime.

---

## `movies.csv`

Contiene:

```text
movieId
title
genres
```

Uso:

- Películas base de MovieLens.
- Título original.
- Géneros iniciales.

---

## `ratings.csv`

Contiene:

```text
userId
movieId
rating
timestamp
```

Uso:

- Base del colaborativo.
- Cálculo de rating count y rating medio.

No conviene abrirlo a mano porque es enorme.

---

## `tags.csv`

Contiene tags de usuarios.

Uso:

- Señales de contenido.
- `userTags`.

---

## `links.csv`

Contiene:

```text
movieId
imdbId
tmdbId
```

Uso:

- Relacionar MovieLens con TMDB/IMDb.

Es clave para no emparejar películas por título.

---

# 3. JSONs procesados

## `ml_32m_summary.json`

Generado por:

```bash
python -m app.scripts.inspect_movielens_32m
```

Sirve para revisar el dataset bruto.

Contiene:

- Total de películas.
- Total de ratings.
- Total de tags.
- Usuarios únicos.
- Cobertura de IDs.
- Rango de años.
- Top películas por ratings.

---

## `ml_32m_candidates.json`

Generado por:

```bash
python -m app.scripts.build_movielens_32m_candidates
```

Sirve para guardar candidatas antes de TMDB.

Contiene películas filtradas por datos, año, ratings y score.

---

## `ml_32m_tmdb_enriched.json`

Generado por:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --resume
```

Contiene candidatas enriquecidas con TMDB.

Tiene mucha información y no es cómodo para revisión manual.

---

## `ml_32m_tmdb_inspection.json`

Generado por:

```bash
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
```

Sirve para revisar cobertura del enriquecimiento:

- Pósters.
- Keywords.
- Certificaciones.
- Géneros.
- Años.
- Suitability.

---

## `ml_32m_demo_catalog.json`

Generado por:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
```

Es el catálogo demo principal.

Contiene:

```text
source
summary
publicCatalog
collaborativeCore
excludedOrSensitive
```

### `publicCatalog`

Películas que verá el público.

### `collaborativeCore`

Películas internas para futuro colaborativo.

### `excludedOrSensitive`

Películas descartadas del catálogo público.

---

# 4. CSVs de revisión

## `ml_32m_demo_catalog_public.csv`

El más importante para revisar la app.

Contiene las películas visibles.

Útil para responder:

- ¿Qué películas ve la gente?
- ¿Hay títulos en español?
- ¿Son modernas/reconocibles?
- ¿Hay algo que no debería estar?

---

## `ml_32m_demo_catalog_collaborative_core.csv`

Contiene películas internas para colaborativo.

Útil para:

- Ver qué base colaborativa tenemos.
- Ver qué películas tienen suficientes datos.
- Revisar solapamiento con catálogo público.

---

## `ml_32m_demo_catalog_excluded.csv`

Contiene películas excluidas.

Útil para:

- Ver qué se descarta.
- Ver motivos de exclusión.
- Ajustar filtros.

---

# 5. Ratings procesados

## `ml_32m_demo_ratings.csv`

Generado por:

```bash
python -m app.scripts.build_demo_ratings_from_movielens_32m
```

Contiene ratings filtrados a películas de `collaborativeCore`.

Columnas:

```text
userId
movieId
rating
timestamp
```

No conviene abrirlo manualmente porque puede tener millones de filas.

---

## `ml_32m_demo_ratings_by_movie.csv`

Resumen por película.

Columnas típicas:

```text
movieId
title
year
isPublicCatalog
isCollaborativeCore
isExcludedOrSensitive
catalogRatingCount
catalogAverageRating
filteredRatingCount
filteredAverageRating
```

Este sí conviene mirarlo.

Sirve para comprobar:

- Si todas las públicas tienen ratings.
- Si todas las collaborative core tienen ratings.
- Cuántos ratings tiene cada película.

---

## `ml_32m_demo_ratings_summary.json`

Resumen global del filtrado.

Campos:

```text
sourceDataset
sourceRatingsRead
ratingsWritten
uniqueUsers
publicCatalogMovies
collaborativeCoreMovies
excludedOrSensitiveMovies
moviesWithFilteredRatings
publicCatalogMoviesWithFilteredRatings
collaborativeCoreMoviesWithFilteredRatings
```

Sirve para confirmar cobertura de un vistazo.

---

# 6. SQLite runtime

## `catalog.sqlite`

Generado por:

```bash
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

Es lo que lee la API en runtime.

Contiene:

- Películas.
- Géneros.
- Tags.
- Notas de cobertura.
- Flags de catálogo.
- Títulos/display fields.

---

# 7. Qué mirar según la pregunta

## ¿Qué películas ve la gente?

```text
ml_32m_demo_catalog_public.csv
```

## ¿Qué películas están excluidas?

```text
ml_32m_demo_catalog_excluded.csv
```

## ¿Qué películas sirven para colaborativo?

```text
ml_32m_demo_catalog_collaborative_core.csv
```

## ¿Tenemos ratings suficientes?

```text
ml_32m_demo_ratings_by_movie.csv
ml_32m_demo_ratings_summary.json
```

## ¿Qué usa realmente la API?

```text
catalog.sqlite
```

---

# 8. Qué se puede regenerar

## Si borras `catalog.sqlite`

Regenerar con:

```bash
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

## Si borras `processed/`

Hay que volver a ejecutar la pipeline de procesamiento.

## Si borras `raw/`

Hay que volver a descargar MovieLens.

---

# 9. Qué no subir a git

No subir:

```text
ml-32m.zip
movies.csv
ratings.csv
tags.csv
links.csv
ml_32m_*.json
ml_32m_*.csv
catalog.sqlite
```

Sí subir:

- Código.
- Scripts.
- README.
- `.gitignore`.

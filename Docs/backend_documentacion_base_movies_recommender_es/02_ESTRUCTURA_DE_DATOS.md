# 02 — Estructura de datos: raw, pipeline_cache y offline_dataset

El backend usa tres niveles de datos. Entender esto es clave.

---

## 1. `raw/`

Ruta:

```text
Backend/app/data/raw/
```

Qué contiene:

```text
MovieLens 32M original descargado y extraído.
```

Dentro de MovieLens 32M hay CSV originales como:

```text
movies.csv
ratings.csv
tags.csv
links.csv
```

Uso:

- es la fuente original;
- permite reconstruir candidatos y ratings;
- no se usa directamente en runtime.

Ejemplo conceptual:

```text
raw/movielens/ml-32m/ml-32m/ratings.csv
```

Contiene decenas de millones de valoraciones.

---

## 2. `pipeline_cache/`

Ruta:

```text
Backend/app/data/pipeline_cache/movielens_32m/
```

Qué contiene:

```text
Artefactos intermedios/caché de la pipeline.
```

No es runtime. Sirve para no repetir pasos caros cada vez.

Archivos principales:

```text
source_dataset_summary.json
candidate_movies.json
tmdb_enriched_movies.json
tmdb_enrichment_inspection.json
partitioned_demo_catalog.json
filtered_collaborative_ratings.csv
filtered_collaborative_ratings_by_movie.csv
filtered_collaborative_ratings_summary.json
```

### Para qué sirve cada uno

#### `source_dataset_summary.json`

Resumen del dataset MovieLens raw.

Sirve para saber:

```text
número de películas
número de ratings
número de tags
usuarios únicos
años disponibles
cobertura de tmdbId/imdbId
```

#### `candidate_movies.json`

Lista de candidatas seleccionadas desde MovieLens antes de llamar a TMDB.

Incluye:

```text
movieId
title
cleanTitle
year
genres de MovieLens
ratingCount
averageRating
tmdbId
imdbId
userTags
candidateScore
dataReliabilityScore
recencyScore
```

Sirve para no procesar las 87.000 películas completas cada vez.

#### `tmdb_enriched_movies.json`

Caché más importante si queremos evitar llamadas a TMDB.

Contiene candidatas enriquecidas con:

```text
overview
displayTitle
displayOverview
posterPath
backdropPath
genres
displayGenres
keywords
topCast
directors
certifications
runtime
originalLanguage
tmdbPopularity
tmdbVoteAverage
tmdbVoteCount
```

Si se borra, para reconstruir el dataset con metadata actualizada habrá que llamar otra vez a TMDB.

#### `tmdb_enrichment_inspection.json`

Resumen de calidad del enriquecimiento TMDB.

Sirve para auditar:

```text
cuántas películas tienen póster
cuántas tienen keywords
cuántas tienen certificaciones ES/US
distribución por suitability
top por rating/popularidad
```

#### `partitioned_demo_catalog.json`

Catálogo ya particionado por la heurística actual.

Contiene:

```text
publicCatalog
collaborativeCore
excludedOrSensitive
```

Este archivo es la base desde la que se exporta el dataset final offline.

#### `filtered_collaborative_ratings.csv`

Ratings filtrados desde el `ratings.csv` gigante de MovieLens.

Contiene filas:

```text
userId,movieId,rating,timestamp
```

Sirve para no volver a recorrer 32 millones de ratings cada vez.

#### `filtered_collaborative_ratings_by_movie.csv`

Resumen técnico por película del filtrado de ratings.

Sirve para saber:

```text
cuántos ratings filtrados tiene cada película
media filtrada
si estaba en publicCatalog/collaborativeCore/excluded
```

#### `filtered_collaborative_ratings_summary.json`

Resumen global del filtrado.

Ejemplo de información:

```text
ratings leídos
ratings escritos
usuarios únicos
películas públicas con ratings
películas collaborativeCore con ratings
```

---

## 3. `offline_dataset/`

Ruta:

```text
Backend/app/data/offline_dataset/
```

Este es el dataset final portable y runtime.

Estructura:

```text
offline_dataset/
├── manifest.json
├── csv/
│   ├── public_movies.csv
│   ├── collaborative_support_movies.csv
│   ├── excluded_movies.csv
│   ├── movie_ratings_summary.csv
│   └── collaborative_ratings.csv
└── images/
    └── posters/
        └── {movieId}.jpg
```

Uso:

- lo usa el backend en runtime;
- lo puede usar una app C++/VR;
- no depende de internet;
- no necesita SQLite;
- no llama a TMDB.

---

## Diferencia resumida

```text
raw/
    Fuente original.

pipeline_cache/
    Cocina/caché para reconstruir.

offline_dataset/
    Resultado final que usa la app.
```

---

## ¿Puedo borrar `pipeline_cache/`?

Sí, pero perderás caché. Si quieres reconstruir todo desde cero, puedes borrarlo.

Si lo borras y mantienes `raw/`, podrás regenerar con los scripts, pero tendrás que volver a llamar a TMDB para crear de nuevo `tmdb_enriched_movies.json`.

---

## ¿Puedo borrar `raw/`?

Sí, pero entonces tendrás que volver a descargar MovieLens 32M si quieres reconstruir desde cero.

---

## ¿Qué hace falta para ejecutar la app?

Para runtime:

```text
offline_dataset/
```

No hace falta:

```text
raw/
pipeline_cache/
```


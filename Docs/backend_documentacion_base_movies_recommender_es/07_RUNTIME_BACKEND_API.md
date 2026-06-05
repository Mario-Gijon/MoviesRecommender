# 07 — Runtime backend y API

Este documento explica cómo funciona el backend cuando la app está en marcha.

---

## Fuente runtime

El runtime usa:

```text
Backend/app/data/offline_dataset/csv/public_movies.csv
```

No usa:

```text
SQLite
TMDB API
image.tmdb.org como fuente en frontend
pipeline_cache
raw
```

---

## Carga del catálogo

Archivo:

```text
Backend/app/infrastructure/catalog/offline_catalog_repository.py
```

Al crearse el repositorio:

1. Lee `manifest.json` si existe.
2. Lee `public_movies.csv`.
3. Convierte cada fila CSV en un diccionario de película de API.
4. Guarda las películas públicas en memoria.

Si falta `public_movies.csv`, lanza un error claro indicando que hay que ejecutar:

```text
python -m app.scripts.export_offline_dataset_from_movielens_32m
```

---

## Pósters locales

El backend monta:

```text
/offline/posters
```

sobre:

```text
Backend/app/data/offline_dataset/images/posters/
```

Una película pública puede tener:

```text
posterUrl = /offline/posters/{movieId}.jpg
```

Ejemplo:

```text
/offline/posters/286897.jpg
```

Si el archivo no existe, `posterUrl` puede ser `None`.

---

## Conversión CSV → API Movie

Por cada fila del CSV público, el backend construye:

```text
id
tmdbId
movieLensId
imdbId
title
originalTitle
year
overview
displayTitle
displayOverview
posterUrl
genres
displayGenres
tags
coverage
```

### `id`

Se usa `movieId`.

### `movieLensId`

También usa `movieId`.

### `displayTitle` y `displayOverview`

Se devuelven si existen. Si no, fallback al título/overview canónico.

### `genres` y `displayGenres`

Se separan usando `|`.

### `tags`

Se construye combinando:

```text
keywords + userTags
```

sin duplicados.

---

## Coverage runtime

Como el runtime ya no lee SQLite, calcula cobertura desde el CSV.

### `availableForContent`

True si existe alguno:

```text
genres
keywords
userTags
overview
```

### `availableForCollaborative`

True si:

```text
filteredRatingCount > 0
```

o si no está disponible:

```text
ratingCount > 0
```

### `contentCoverage`

Score basado en presencia de:

```text
overview      0.35
genres        0.25
keywords      0.20
userTags      0.20
```

Máximo 1.0.

### `collaborativeCoverage`

Score basado en volumen de ratings:

```text
min(1.0, rating_volume / 250)
```

Por tanto, una película con 250 ratings o más tiene cobertura colaborativa 1.0.

---

# Endpoints

## `GET /catalog/status`

Devuelve estado del catálogo.

Ahora indica:

```text
dataMode = offline-csv-dataset
sources = offline_dataset, movielens, tmdb
```

Notas:

```text
Runtime catalog is loaded from the portable offline CSV dataset.
Posters are served locally from /offline/posters.
No external APIs are used at runtime.
```

---

## `GET /movies/featured`

Devuelve todas las películas públicas cargadas desde CSV.

---

## `GET /movies/public-catalog`

Parámetros:

```text
page
pageSize
search
genre
```

Devuelve:

```text
items
page
pageSize
totalItems
totalPages
```

### Búsqueda

Busca en:

```text
title
originalTitle
displayTitle
genres
displayGenres
tags
```

### Filtro de género

Compara con:

```text
genres
displayGenres
```

### Orden

Conserva el orden de `public_movies.csv`.

---

## `POST /recommendations`

Ahora mismo usa placeholder.

Archivo:

```text
Backend/app/domain/recommendations/recommendation_strategy.py
```

Regla importante:

```text
get_recommendation_candidates() devuelve solo public_movies.
```

Así que aunque exista `collaborative_support_movies.csv`, todavía no se usa ni se expone.

---

## Seguridad de catálogo

Runtime no lee:

```text
collaborative_support_movies.csv
excluded_movies.csv
```

para catálogo público.

El soporte colaborativo se usará más adelante en el recomendador, pero nunca debe devolverse como recomendación final directa.

---

## Frontend

El frontend puede seguir usando `movie.posterUrl`.

Si la API devuelve:

```text
/offline/posters/{movieId}.jpg
```

el cliente debe resolverlo contra la base del backend:

```text
http://localhost:8014/offline/posters/{movieId}.jpg
```

---

## Qué no pasa en runtime

En runtime no se llama a:

```text
TMDB API
MovieLens
SQLite
scripts de pipeline
```

La app solo lee ficheros locales.


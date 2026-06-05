# 10 — Glosario rápido

## MovieLens 32M

Dataset público con películas, ratings, tags y enlaces a TMDB/IMDb.

Lo usamos como fuente de:

```text
ratings
userId
movieId
averageRating
ratingCount
userTags
tmdbId
imdbId
```

---

## TMDB

The Movie Database.

Lo usamos para enriquecer películas con:

```text
poster
overview
genres
keywords
cast
directors
certifications
displayTitle
displayOverview
displayGenres
runtime
popularity
votes
```

Solo se llama en scripts, no en runtime.

---

## raw

Datos originales descargados.

---

## pipeline_cache

Caché/intermedios de reconstrucción.

Sirve para no repetir llamadas TMDB o escaneos grandes de ratings.

---

## offline_dataset

Dataset final portable que usa la app.

---

## public movies

Películas visibles, valorables y recomendables.

---

## collaborative support movies

Películas internas para cálculo colaborativo.

No se muestran ni se recomiendan directamente.

---

## excluded movies

Películas descartadas del dataset útil.

---

## candidateScore

Score inicial para elegir candidatas desde MovieLens.

Combina fiabilidad, actualidad y disponibilidad de tags.

---

## dataReliabilityScore

Score de fiabilidad de datos.

Tiene en cuenta volumen de ratings, media y existencia de IDs externos.

---

## recencyScore

Score de actualidad basado en año.

---

## standDisplayScore

Score para ordenar películas públicas de forma atractiva para el stand.

---

## demoSuitability

Clasificación para decidir si una película es apta para público joven.

Valores:

```text
family_friendly_candidate
teen_candidate
adult_or_sensitive
unknown
```

---

## ratingCount

Número de ratings de origen MovieLens/catálogo.

---

## filteredRatingCount

Número de ratings que quedaron en el dataset colaborativo filtrado.

---

## averageRating

Media original MovieLens/catálogo.

---

## filteredAverageRating

Media recalculada sobre ratings filtrados.

---

## displayTitle

Título mostrado al usuario, en español si TMDB lo tiene.

---

## displayGenres

Géneros mostrados al usuario, en español si TMDB los tiene.

---

## collaborative_ratings.csv

CSV grande con ratings usuario-película para el futuro recomendador colaborativo.


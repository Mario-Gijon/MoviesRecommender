# Documentación base del backend — Movie Recommender

Este paquete resume cómo está organizado el backend del proyecto **MoviesRecommender**, centrándose en:

- qué datos tenemos de las películas;
- cómo se construye el dataset;
- qué papel tiene cada carpeta (`raw`, `pipeline_cache`, `offline_dataset`);
- qué scripts existen y en qué orden se ejecutan;
- cómo se filtran las películas públicas, colaborativas internas y descartadas;
- cómo funciona ahora mismo el runtime del backend;
- qué queda preparado para empezar el recomendador.

La idea es que puedas leer esto antes de seguir programando y tener una visión mental clara del sistema.

---

## Orden recomendado de lectura

1. `01_MAPA_GENERAL_BACKEND.md`  
   Visión global del backend y de las capas principales.

2. `02_ESTRUCTURA_DE_DATOS.md`  
   Explica `raw`, `pipeline_cache` y `offline_dataset`.

3. `03_PIPELINE_DE_DATOS_Y_SCRIPTS.md`  
   Explica qué hace cada script y en qué orden se ejecuta.

4. `04_DATASET_OFFLINE.md`  
   Explica los CSV finales, imágenes locales y `manifest.json`.

5. `05_DICCIONARIO_CAMPOS_PELICULA.md`  
   Explica cada campo importante de una película.

6. `06_HEURISTICAS_FILTRADO_Y_ORDEN.md`  
   Explica cómo decidimos qué película es pública, soporte colaborativo o descarte.

7. `07_RUNTIME_BACKEND_API.md`  
   Explica cómo funciona ahora el backend en runtime.

8. `08_REGENERAR_DATASET.md`  
   Explica cómo reiniciar la pipeline y reconstruir el dataset.

9. `09_ESTADO_ACTUAL_Y_SIGUIENTE_FASE.md`  
   Resume dónde estamos y cómo abordar el recomendador.

---

## Idea principal

El backend ya no depende de SQLite ni de TMDB en runtime.

Ahora la app usa:

```text
Backend/app/data/offline_dataset/
```

Ese directorio contiene:

```text
csv/public_movies.csv
csv/collaborative_support_movies.csv
csv/excluded_movies.csv
csv/movie_ratings_summary.csv
csv/collaborative_ratings.csv
images/posters/{movieId}.jpg
manifest.json
```

El backend carga el catálogo público desde CSV y sirve los pósters desde disco. Por tanto, para la demo/stand, la app puede funcionar sin internet si ya existe `offline_dataset`.

---

## Resumen corto

```text
raw/
    Dataset original de MovieLens 32M.

pipeline_cache/
    Caché/intermedios para reconstruir el dataset sin repetir pasos caros.

offline_dataset/
    Dataset final portable y runtime.
```

MovieLens aporta:

```text
ratings, userId, movieId, tags, tmdbId, imdbId, ratingCount, averageRating
```

TMDB aporta:

```text
posterPath, overview, displayTitle, displayOverview, genres, displayGenres,
keywords, cast, directors, certifications, runtime, popularity, votes
```

El dataset final separa:

```text
public_movies.csv
    Películas visibles, valorables y recomendables.

collaborative_support_movies.csv
    Películas internas para el modelo colaborativo. No se muestran.

excluded_movies.csv
    Películas descartadas técnicamente o no útiles.
```

---

## Estado actual de conteos

Con la ejecución actual validada:

```text
public_movies.csv: 712
collaborative_support_movies.csv: 1258
excluded_movies.csv: 30
movie_ratings_summary.csv: 1970
collaborative_ratings.csv: 7.369.524
posters públicos locales: 712
```

Estos números pueden cambiar si en el futuro modificamos filtros, heurísticas, límite de candidatos o si TMDB devuelve datos distintos.


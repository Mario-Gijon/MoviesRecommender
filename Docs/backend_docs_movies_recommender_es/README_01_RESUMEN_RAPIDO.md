# Backend Movies Recommender — Resumen rápido

Este documento sirve para entender el backend en pocos minutos antes de una llamada.

## 1. Qué es el backend

El backend es una API en **FastAPI** para una demo de recomendación de películas. La fuente activa ya no son datos inventados: el catálogo se prepara con una pipeline offline basada en **MovieLens 32M** y **TMDB**.

La idea general es:

```text
MovieLens 32M + TMDB
        ↓
scripts offline de preparación
        ↓
catalog.sqlite
        ↓
FastAPI
        ↓
Frontend React
```

Durante la demo, la API no debería llamar a TMDB ni leer CSV gigantes. Todo lo pesado se hace antes con scripts.

## 2. Qué aporta cada fuente

### MovieLens 32M

Aporta:

- Películas.
- Ratings de usuarios.
- Tags de usuarios.
- Relación con TMDB e IMDb mediante `links.csv`.

Sirve sobre todo para:

- Saber qué películas tienen muchos datos.
- Calcular `ratingCount` y `averageRating`.
- Preparar recomendación colaborativa futura.
- Usar tags como señales de contenido.

### TMDB

Aporta:

- Póster.
- Backdrop.
- Descripción.
- Géneros.
- Keywords.
- Reparto.
- Directores.
- Certificaciones.
- Popularidad.
- Títulos, descripciones y géneros en español.

Sirve sobre todo para:

- Hacer la app visual.
- Tener metadatos ricos.
- Filtrar contenido sensible.
- Mostrar datos entendibles al público español.

## 3. Qué tenemos ahora

Ahora mismo tenemos tres capas de catálogo:

### `publicCatalog`

Películas visibles para el usuario.

Sirve para:

- Buscar.
- Valorar.
- Mostrar en la app.
- Recibir recomendaciones.

### `collaborativeCore`

Películas internas con datos suficientes para futuro colaborativo.

Sirve para:

- Filtrar ratings.
- Entrenar o construir un modelo colaborativo.
- Tener más evidencia interna aunque algunas películas no sean públicas.

### `excludedOrSensitive`

Películas descartadas del catálogo público.

Motivos habituales:

- Contenido adulto o sensible.
- Falta de póster.
- Falta de datos.
- Año fuera del filtro.
- Suitability desconocida.
- Error al enriquecer con TMDB.

## 4. Qué datos tenemos de cada película

Tenemos:

- IDs: `movieId`, `tmdbId`, `imdbId`.
- Título canónico: `title`, `cleanTitle`, `originalTitle`.
- Título para mostrar: `displayTitle`.
- Descripción canónica: `overview`.
- Descripción para mostrar: `displayOverview`.
- Géneros canónicos: `genres`.
- Géneros para mostrar: `displayGenres`.
- Keywords de TMDB: `keywords`.
- Tags de MovieLens: `userTags`.
- Póster y backdrop.
- Ratings agregados: `ratingCount`, `averageRating`.
- Scores internos: `candidateScore`, `dataReliabilityScore`, `recencyScore`, `standDisplayScore`.
- Datos de TMDB: popularidad, votos, runtime, idioma original, certificaciones, reparto, directores.
- Campos de suitability y exclusión.

## 5. Por qué poner títulos en español no rompe nada

No perdemos ratings ni relaciones porque MovieLens identifica las películas con `movieId`, no con el título.

La relación con TMDB se mantiene con:

```text
tmdbId
imdbId
```

Por eso podemos mostrar:

```text
displayTitle
displayOverview
displayGenres
```

y conservar internamente:

```text
title
overview
genres
keywords
userTags
```

## 6. Archivos importantes para revisar

Para ver las películas públicas:

```text
Backend/app/data/processed/movielens/ml_32m_demo_catalog_public.csv
```

Para ver el núcleo colaborativo:

```text
Backend/app/data/processed/movielens/ml_32m_demo_catalog_collaborative_core.csv
```

Para ver las excluidas:

```text
Backend/app/data/processed/movielens/ml_32m_demo_catalog_excluded.csv
```

Para ver ratings por película:

```text
Backend/app/data/processed/movielens/ml_32m_demo_ratings_by_movie.csv
```

Para resumen de ratings filtrados:

```text
Backend/app/data/processed/movielens/ml_32m_demo_ratings_summary.json
```

## 7. Orden de la pipeline

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

Una vez ya está todo descargado/enriquecido, normalmente trabajarás con:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.export_demo_catalog_32m_review_files
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.seed_demo_catalog_from_movielens_32m
```

## 8. Estado del recomendador

El endpoint `/recommendations` existe, pero la lógica actual sigue siendo placeholder. Lo siguiente será implementar:

1. Recomendador basado en contenido.
2. Recomendador colaborativo.
3. Recomendador híbrido.
4. Explicaciones reales.

La parte importante es que los datos ya están bastante preparados para hacerlo.

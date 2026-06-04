# Guía rápida para llamada — Backend Movies Recommender

Documento corto para explicar el backend en una llamada.

---

## 1. Frase resumen

El backend prepara un catálogo de películas para una demo de recomendación usando MovieLens 32M y TMDB. MovieLens aporta ratings, tags e IDs; TMDB aporta pósters, descripción, géneros, certificaciones y textos en español. Todo se procesa offline y se mete en SQLite para que la API sea rápida durante la demo.

---

## 2. Por qué hay una pipeline

No usamos MovieLens 32M directamente en runtime porque:

- Tiene demasiadas películas.
- Tiene millones de ratings.
- Los CSV son pesados.
- TMDB requiere token e internet.
- La demo tiene que ser estable.

Por eso hacemos:

```text
procesamiento offline → SQLite runtime
```

---

## 3. Qué datos tenemos

De cada película podemos tener:

- `movieId`, `tmdbId`, `imdbId`.
- Título canónico.
- Título en español.
- Descripción canónica.
- Descripción en español.
- Géneros canónicos.
- Géneros en español.
- Keywords TMDB.
- Tags MovieLens.
- Póster.
- Backdrop.
- Rating count.
- Rating medio.
- Popularidad TMDB.
- Certificaciones.
- Reparto.
- Directores.
- Suitability para la demo.

---

## 4. Qué no perdemos al usar español en UI

No perdemos ratings porque MovieLens usa `movieId`.

No perdemos relación con TMDB porque usamos `tmdbId`.

Mostramos al usuario:

```text
displayTitle
displayOverview
displayGenres
```

Pero mantenemos internamente:

```text
title
overview
genres
keywords
userTags
```

---

## 5. Las tres listas clave

## `publicCatalog`

Lo que ve el usuario.

Sirve para:

- Valorar.
- Buscar.
- Recomendar.

## `collaborativeCore`

Películas internas con datos colaborativos suficientes.

Sirve para:

- Futuro colaborativo.
- Filtrar ratings útiles.
- Entrenar modelos o artefactos compactos.

## `excludedOrSensitive`

Películas fuera del catálogo público.

Motivos:

- Contenido sensible.
- Sin póster.
- Sin datos suficientes.
- Año fuera del filtro.
- Suitability desconocida.

---

## 6. Qué archivos enseñaría si preguntan

Para enseñar películas públicas:

```text
ml_32m_demo_catalog_public.csv
```

Para enseñar ratings filtrados:

```text
ml_32m_demo_ratings_summary.json
```

Para enseñar cobertura por película:

```text
ml_32m_demo_ratings_by_movie.csv
```

---

## 7. Qué hace SQLite

SQLite es la base runtime local.

Evita:

- Leer JSON enormes.
- Leer CSV gigantes.
- Llamar a TMDB durante la demo.

La API lee de:

```text
Backend/app/data/catalog.sqlite
```

---

## 8. Estado actual

Hecho:

- Pipeline MovieLens 32M.
- Enriquecimiento TMDB.
- Títulos/géneros/descripciones display en español.
- Catálogo público.
- Núcleo colaborativo.
- Ratings filtrados.
- SQLite runtime.
- API de catálogo paginado.
- Frontend visual.

Pendiente:

- Recomendador real basado en contenido.
- Recomendador colaborativo.
- Recomendador híbrido.
- Explicaciones reales.

---

## 9. Cómo explicar el recomendador futuro

### Basado en contenido

Usará:

- Géneros.
- Keywords.
- Tags.
- Overview.
- Películas valoradas por el usuario.

### Colaborativo

Usará:

- Ratings históricos filtrados.
- Películas del collaborative core.
- Ratings actuales del usuario.

No debería leer millones de ratings en runtime. Lo normal será crear un modelo o artefacto compacto offline.

### Híbrido

Combinará:

```text
contentScore + collaborativeScore + popularidad/diversidad
```

---

## 10. Orden de scripts si preguntan

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

---

## 11. Respuesta corta a “por qué no usar todo MovieLens”

Porque para una demo pública necesitamos un catálogo:

- Reconocible.
- Visual.
- Con pósters.
- Con datos suficientes.
- Sin contenido sensible.
- Rápido.
- Manejable.

Por eso filtramos y preparamos un catálogo demo.

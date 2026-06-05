# 08 — Regenerar el dataset

Este documento explica cómo reconstruir el dataset desde cero o parcialmente.

---

## Conceptos

```text
raw/
    MovieLens original. Si lo conservas, no tienes que descargar de nuevo.

pipeline_cache/
    Caché/intermedios. Se puede borrar y regenerar.

offline_dataset/
    Dataset final/runtime. Se puede borrar y regenerar.
```

---

# Regeneración completa manteniendo `raw/`

Si quieres reiniciar todo, pero no volver a descargar MovieLens:

```bash
cd /home/mario/Documents/Trabalo/AppRecommender/NewRecommenderApp/Backend

rm -rf app/data/pipeline_cache
rm -rf app/data/offline_dataset

python -m app.scripts.inspect_movielens_32m
python -m app.scripts.build_movielens_32m_candidates
python -m app.scripts.enrich_movielens_32m_with_tmdb
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.export_offline_dataset_from_movielens_32m
python -m app.scripts.download_offline_movie_posters
```

Esto:

```text
recalcula candidatos
vuelve a llamar a TMDB
recalcula heurísticas
regenera CSV offline
redescarga posters
```

---

# Regeneración sin volver a llamar a TMDB

Si conservas:

```text
pipeline_cache/movielens_32m/tmdb_enriched_movies.json
```

y solo cambias heurísticas de filtrado/orden, puedes ejecutar desde ahí:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.build_demo_ratings_from_movielens_32m
python -m app.scripts.export_offline_dataset_from_movielens_32m
python -m app.scripts.download_offline_movie_posters
```

Esto evita llamar a TMDB.

---

# Regenerar solo `offline_dataset`

Si ya tienes:

```text
partitioned_demo_catalog.json
filtered_collaborative_ratings.csv
filtered_collaborative_ratings_by_movie.csv
```

puedes ejecutar:

```bash
python -m app.scripts.export_offline_dataset_from_movielens_32m
python -m app.scripts.download_offline_movie_posters
```

---

# Regenerar solo pósters

Si el CSV público ya existe:

```bash
python -m app.scripts.download_offline_movie_posters
```

Forzar redescarga:

```bash
python -m app.scripts.download_offline_movie_posters --force
```

Prueba limitada:

```bash
python -m app.scripts.download_offline_movie_posters --limit 10
```

---

# Si borras `pipeline_cache/`

La app sigue funcionando si `offline_dataset/` existe.

Pero si luego quieres reconstruir, tendrás que regenerar los intermedios.

---

# Si borras `offline_dataset/`

La app no podrá arrancar correctamente hasta que vuelvas a exportar:

```bash
python -m app.scripts.export_offline_dataset_from_movielens_32m
python -m app.scripts.download_offline_movie_posters
```

---

# Si borras `raw/`

Tendrás que volver a descargar MovieLens:

```bash
python -m app.scripts.download_movielens_32m
```

---

# Resultado esperado actual

Con la lógica actual, al reconstruir deberías obtener aproximadamente:

```text
public_movies.csv: 712
collaborative_support_movies.csv: 1258
excluded_movies.csv: 30
movie_ratings_summary.csv: 1970
collaborative_ratings.csv: 7.369.524
posters públicos: 712
```

Puede cambiar si TMDB devuelve datos actualizados o si modificas heurísticas.

---

# Qué puede cambiar si se llama otra vez a TMDB

TMDB puede cambiar:

```text
popularity
voteAverage
voteCount
certifications
keywords
overview
displayOverview
posterPath
```

Por eso una regeneración completa puede no ser byte a byte idéntica a la actual.


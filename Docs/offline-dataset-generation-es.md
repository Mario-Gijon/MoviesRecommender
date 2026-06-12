# Dataset offline

## Comando recomendado

Comando base para generar el dataset offline sin auditoría (suponiendo que tenemos un entorno virtual de python .venv):

```bash
cd Backend
source .venv/bin/activate

python -m app.scripts.run_movielens_32m_pipeline \
  --download-raw-movielens \
  --candidate-limit 15000 \
  --candidate-min-ratings 100 \
  --candidate-min-year 1990 \
  --collaborative-core-limit 15000 \
  --public-min-year 2000 \
  --collaborative-min-year 1990
```

Si también quieres generar el dashboard de auditoría:

```bash
python -m app.scripts.run_movielens_32m_pipeline \
  --download-raw-movielens \
  --candidate-limit 15000 \
  --candidate-min-ratings 100 \
  --candidate-min-year 1990 \
  --collaborative-core-limit 15000 \
  --public-min-year 2000 \
  --collaborative-min-year 1990 \
  --audit
```

---

## Parámetros del script

| Parámetro | Significado | Valor recomendado |
| --- | --- | --- |
| `--download-raw-movielens` | Descarga MovieLens 32M si no están los ficheros raw. | Usarlo en la primera ejecución |
| `--candidate-limit` | Límite máximo de películas candidatas iniciales. | `15000` |
| `--candidate-min-ratings` | Mínimo de ratings MovieLens para considerar una película candidata. | `100` |
| `--candidate-min-year` | Año mínimo para las candidatas iniciales. | `1990` |
| `--candidate-max-year` | Año máximo para candidatas iniciales. | Opcional |
| `--max-tags-per-movie` | Máximo de tags de usuario guardados por película. | Por defecto `35` |
| `--resume-tmdb` | Reutiliza el cache existente de TMDB. | Por defecto |
| `--no-resume-tmdb` | No reutiliza el cache de TMDB. | Solo si quieres forzar |
| `--public-limit` | Limita el número de películas públicas. | No usar normalmente |
| `--collaborative-core-limit` | Límite del núcleo colaborativo. | `15000` |
| `--catalog-min-ratings` | Mínimo de ratings usado en la fase de catálogo. | Por defecto `100` |
| `--public-min-year` | Año mínimo para películas visibles en catálogo público. | `2000` |
| `--collaborative-min-year` | Año mínimo para películas usadas en soporte colaborativo. | `1990` |
| `--family-only` | Genera un catálogo público solo con películas familiares. | No usar normalmente |
| `--skip-posters` | Omite descarga/reutilización de pósteres. | Opcional |
| `--audit` | Genera el dashboard de auditoría. | Opcional |
| `--dry-run` | Muestra qué etapas se ejecutarían sin ejecutarlas. | Opcional |
| `--start-at` | Empieza desde una fase concreta. Valores: `candidates`, `enrich`, `catalog`, `ratings`, `export`, `posters`, `audit`. | Útil para regenerar parcialmente |
| `--stop-after` | Termina después de una fase concreta. | Opcional |

---

## CSVs generados

Los CSV finales se generan en:

```txt
Backend/app/data/offline_dataset/csv/
```

---

## `public_movies.csv`

Ruta:

```txt
Backend/app/data/offline_dataset/csv/public_movies.csv
```

Propósito:

Películas visibles y recomendables para el usuario final. El recomendador final debe recomendar desde este CSV.

Columnas:

```txt
movieId, tmdbId, imdbId, title, cleanTitle, originalTitle, displayTitle,
year, overview, displayOverview, genres, displayGenres, keywords,
userTags, topCast, directors, posterPath, posterFile, runtime,
originalLanguage, ratingCount, averageRating, filteredRatingCount,
filteredAverageRating, candidateScore, dataReliabilityScore,
recencyScore, tmdbPopularity, tmdbVoteAverage, tmdbVoteCount,
suitabilityCategory, standDisplayScore, standDisplayReasons
```

---

## `collaborative_support_movies.csv`

Ruta:

```txt
Backend/app/data/offline_dataset/csv/collaborative_support_movies.csv
```

Propósito:

Películas que no son visibles ni recomendables directamente, pero se conservan para aportar señal colaborativa.

Columnas:

```txt
movieId, tmdbId, imdbId, title, cleanTitle, originalTitle, displayTitle,
year, overview, displayOverview, genres, displayGenres, keywords,
userTags, topCast, directors, posterPath, posterFile, runtime,
originalLanguage, ratingCount, averageRating, filteredRatingCount,
filteredAverageRating, candidateScore, dataReliabilityScore,
recencyScore, tmdbPopularity, tmdbVoteAverage, tmdbVoteCount,
suitabilityCategory, standDisplayScore, standDisplayReasons,
publicExclusionReasons, publicBlockedTerms, suitabilityReasons
```

---

## `excluded_movies.csv`

Ruta:

```txt
Backend/app/data/offline_dataset/csv/excluded_movies.csv
```

Propósito:

Películas excluidas del dataset offline final.

Columnas:

```txt
movieId, tmdbId, imdbId, title, cleanTitle, originalTitle, displayTitle,
year, overview, displayOverview, genres, displayGenres, keywords,
userTags, topCast, directors, posterPath, posterFile, runtime,
originalLanguage, ratingCount, averageRating, filteredRatingCount,
filteredAverageRating, candidateScore, dataReliabilityScore,
recencyScore, tmdbPopularity, tmdbVoteAverage, tmdbVoteCount,
suitabilityCategory, standDisplayScore, standDisplayReasons,
publicExclusionReasons, publicBlockedTerms, suitabilityReasons,
exclusionCategory, exclusionReasons
```

---

## `collaborative_ratings.csv`

Ruta:

```txt
Backend/app/data/offline_dataset/csv/collaborative_ratings.csv
```

Propósito:

Ratings usados por los componentes colaborativos del recomendador.

Columnas:

```txt
userId, movieId, rating, timestamp
```

---

## `movie_ratings_summary.csv`

Ruta:

```txt
Backend/app/data/offline_dataset/csv/movie_ratings_summary.csv
```

Propósito:

Resumen de ratings por película.

Columnas:

```txt
movieId, title, displayTitle, datasetRole, ratingCount,
averageRating, filteredRatingCount, filteredAverageRating
```

---

## Significado de las particiones

| Partición | Significado |
| --- | --- |
| `public` | Películas visibles y recomendables para el usuario final. |
| `collaborative_support` | Películas ocultas, pero útiles como señal colaborativa. |
| `excluded` | Películas fuera del dataset offline final. |

---

## Significado de los scores y métricas principales

### `candidateScore`

Score inicial usado para ordenar las películas candidatas antes de construir el catálogo final.

Combina señales como:

- fiabilidad de datos
- recencia
- cantidad de tags de usuario

No representa directamente si una película debe mostrarse al público. Sirve sobre todo en la fase inicial de selección de candidatas.

---

### `dataReliabilityScore`

Mide la fiabilidad de los datos de MovieLens para una película.

Tiene en cuenta principalmente:

- `ratingCount`
- `averageRating`

Una película con muchos ratings y buena media tendrá mayor `dataReliabilityScore`.

---

### `recencyScore`

Mide cómo de reciente es una película según su año.

Se usa para favorecer películas culturalmente más actuales sin eliminar necesariamente películas antiguas.

---

### `standDisplayScore`

Score principal para ordenar y filtrar el catálogo público.

Representa cómo de adecuada/interesante es una película para mostrarse en el stand.

Tiene en cuenta señales como:

- categoría de adecuación (`suitabilityCategory`)
- atractivo de géneros
- popularidad/reconocimiento
- recencia
- términos positivos
- fiabilidad de datos
- penalizaciones por señales sensibles

Las películas públicas deben superar el mínimo configurado de `0.39`.

---

### `standDisplayReasons`

Razones explicativas del `standDisplayScore`.

Ejemplos:

```txt
stand_family_suitability
stand_teen_suitability
strong_stand_genre_appeal
moderate_public_recognition
recent_movie
positive_audience_terms
strong_movielens_data
sensitive_genre_display_penalty
```

Sirve para auditoría y explicación interna del ranking.

---

### `suitabilityCategory`

Clasificación de adecuación de la película.

Valores principales:

| Valor | Significado |
| --- | --- |
| `family_friendly` | Película apta para público familiar. |
| `teen` | Película apta para público adolescente/general. |
| `adult_or_sensitive` | Película adulta o sensible. No debe estar en catálogo público. |
| `unknown` | No hay suficientes señales claras de adecuación. |

---

### `publicExclusionReasons`

Razones por las que una película no entra en `public_movies.csv`.

Ejemplos:

```txt
adult_or_sensitive
blocked_public_topic
low_stand_display_score
low_stand_accessibility
below_public_min_year
unknown_suitability
```

Una película con `publicExclusionReasons` puede seguir apareciendo en `collaborative_support_movies.csv` si es útil para el sistema colaborativo.

---

### `publicBlockedTerms`

Términos sensibles detectados que bloquean una película para el catálogo público.

Ejemplos:

```txt
drug
gore
murder
nazi
terrorism
suicide
torture
```

---

### `suitabilityReasons`

Razones usadas para decidir la categoría de adecuación (`suitabilityCategory`).

Sirve para entender por qué una película se considera familiar, adolescente, adulta/sensible o desconocida.

---

### `ratingCount`

Número total de ratings de MovieLens para esa película antes del filtrado final.

---

### `averageRating`

Media de rating de MovieLens para esa película antes del filtrado final.

---

### `filteredRatingCount`

Número de ratings conservados para esa película dentro del dataset colaborativo offline.

---

### `filteredAverageRating`

Media de rating usando solo los ratings filtrados del dataset colaborativo offline.

---

### `tmdbPopularity`

Popularidad de la película según TMDB.

No es un score normalizado de 0 a 1. Es una métrica propia de TMDB y se usa como señal de reconocimiento público.

---

### `tmdbVoteAverage`

Media de votos de TMDB.

---

### `tmdbVoteCount`

Número de votos de TMDB.

---

## Regenerar parcialmente

Desde `catalog` en adelante:

```bash
cd Backend
source .venv/bin/activate

python -m app.scripts.run_movielens_32m_pipeline \
  --start-at catalog \
  --candidate-limit 15000 \
  --candidate-min-ratings 100 \
  --candidate-min-year 1990 \
  --collaborative-core-limit 15000 \
  --public-min-year 2000 \
  --collaborative-min-year 1990
```

Solo auditoría:

```bash
cd Backend
source .venv/bin/activate

python -m app.scripts.run_movielens_32m_pipeline \
  --start-at audit \
  --audit
```

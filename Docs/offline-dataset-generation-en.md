# Offline dataset

## Recommended command

Base command to generate the offline dataset without the audit dashboard (assuming we have created a Python Virtual Environment .venv):

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

If you also want to generate the audit dashboard:

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

## Script parameters

| Parameter | Meaning | Recommended value |
| --- | --- | --- |
| `--download-raw-movielens` | Downloads MovieLens 32M if the raw files are not available. | Use it on the first run |
| `--candidate-limit` | Maximum number of initial candidate movies. | `15000` |
| `--candidate-min-ratings` | Minimum number of MovieLens ratings required for a movie to become a candidate. | `100` |
| `--candidate-min-year` | Minimum year for initial candidate movies. | `1990` |
| `--candidate-max-year` | Maximum year for initial candidate movies. | Optional |
| `--max-tags-per-movie` | Maximum number of user tags stored per movie. | Default `35` |
| `--resume-tmdb` | Reuses the existing TMDB cache. | Default |
| `--no-resume-tmdb` | Does not reuse the existing TMDB cache. | Only if you need to force it |
| `--public-limit` | Limits the number of public movies. | Usually not used |
| `--collaborative-core-limit` | Limit for the collaborative core. | `15000` |
| `--catalog-min-ratings` | Minimum number of ratings used in the catalog stage. | Default `100` |
| `--public-min-year` | Minimum year for movies visible in the public catalog. | `2000` |
| `--collaborative-min-year` | Minimum year for movies used as collaborative support. | `1990` |
| `--family-only` | Generates a public catalog containing only family-friendly movies. | Usually not used |
| `--skip-posters` | Skips poster download/reuse. | Optional |
| `--audit` | Generates the audit dashboard. | Optional |
| `--dry-run` | Shows which stages would run without executing them. | Optional |
| `--start-at` | Starts from a specific stage. Values: `candidates`, `enrich`, `catalog`, `ratings`, `export`, `posters`, `audit`. | Useful for partial regeneration |
| `--stop-after` | Stops after a specific stage. | Optional |

---

## Generated CSV files

The final CSV files are generated in:

```txt
Backend/app/data/offline_dataset/csv/
```

---

## `public_movies.csv`

Path:

```txt
Backend/app/data/offline_dataset/csv/public_movies.csv
```

Purpose:

Movies visible and recommendable to the final user. Final recommendations should come from this CSV.

Columns:

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

Path:

```txt
Backend/app/data/offline_dataset/csv/collaborative_support_movies.csv
```

Purpose:

Movies that are not directly visible or recommendable, but are kept as collaborative support signal.

Columns:

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

Path:

```txt
Backend/app/data/offline_dataset/csv/excluded_movies.csv
```

Purpose:

Movies excluded from the final offline dataset.

Columns:

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

Path:

```txt
Backend/app/data/offline_dataset/csv/collaborative_ratings.csv
```

Purpose:

Ratings used by the collaborative components of the recommender.

Columns:

```txt
userId, movieId, rating, timestamp
```

---

## `movie_ratings_summary.csv`

Path:

```txt
Backend/app/data/offline_dataset/csv/movie_ratings_summary.csv
```

Purpose:

Movie-level ratings summary.

Columns:

```txt
movieId, title, displayTitle, datasetRole, ratingCount,
averageRating, filteredRatingCount, filteredAverageRating
```

---

## Partition meaning

| Partition | Meaning |
| --- | --- |
| `public` | Movies visible and recommendable to the final user. |
| `collaborative_support` | Hidden movies that are still useful as collaborative signal. |
| `excluded` | Movies outside the final offline dataset. |

---

## Meaning of the main scores and metrics

### `candidateScore`

Initial score used to rank candidate movies before building the final catalog.

It combines signals such as:

- data reliability
- recency
- number of user tags

It does not directly represent whether a movie should be shown to the public. It is mainly used during the initial candidate selection stage.

---

### `dataReliabilityScore`

Measures how reliable the MovieLens data is for a movie.

It mainly considers:

- `ratingCount`
- `averageRating`

A movie with many ratings and a good average rating will have a higher `dataReliabilityScore`.

---

### `recencyScore`

Measures how recent a movie is according to its year.

It is used to favor more culturally current movies without necessarily removing older movies.

---

### `standDisplayScore`

Main score used to rank and filter the public catalog.

It represents how suitable/interesting a movie is for being shown on the stand.

It considers signals such as:

- suitability category (`suitabilityCategory`)
- genre appeal
- popularity/recognition
- recency
- positive terms
- data reliability
- penalties for sensitive signals

Public movies must pass the configured minimum value of `0.39`.

---

### `standDisplayReasons`

Explanatory reasons behind the `standDisplayScore`.

Examples:

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

Used for auditing and internal explanation of the ranking.

---

### `suitabilityCategory`

Movie suitability classification.

Main values:

| Value | Meaning |
| --- | --- |
| `family_friendly` | Movie suitable for a family audience. |
| `teen` | Movie suitable for a teen/general audience. |
| `adult_or_sensitive` | Adult or sensitive movie. It must not be part of the public catalog. |
| `unknown` | There are not enough clear suitability signals. |

---

### `publicExclusionReasons`

Reasons why a movie is not included in `public_movies.csv`.

Examples:

```txt
adult_or_sensitive
blocked_public_topic
low_stand_display_score
low_stand_accessibility
below_public_min_year
unknown_suitability
```

A movie with `publicExclusionReasons` can still appear in `collaborative_support_movies.csv` if it is useful for the collaborative system.

---

### `publicBlockedTerms`

Sensitive terms detected that block a movie from the public catalog.

Examples:

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

Reasons used to decide the suitability category (`suitabilityCategory`).

Used to understand why a movie is considered family-friendly, teen, adult/sensitive, or unknown.

---

### `ratingCount`

Total number of MovieLens ratings for that movie before the final filtering.

---

### `averageRating`

Average MovieLens rating for that movie before the final filtering.

---

### `filteredRatingCount`

Number of ratings kept for that movie inside the offline collaborative dataset.

---

### `filteredAverageRating`

Average rating using only the filtered ratings from the offline collaborative dataset.

---

### `tmdbPopularity`

Movie popularity according to TMDB.

It is not a normalized score from 0 to 1. It is TMDB's own metric and is used as a public recognition signal.

---

### `tmdbVoteAverage`

Average TMDB vote score.

---

### `tmdbVoteCount`

Number of TMDB votes.

---

## Partial regeneration

From `catalog` onward:

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

Audit only:

```bash
cd Backend
source .venv/bin/activate

python -m app.scripts.run_movielens_32m_pipeline \
  --start-at audit \
  --audit
```

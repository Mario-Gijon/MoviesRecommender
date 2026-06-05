# 06 — Heurísticas de filtrado y orden

Este documento explica por qué acabamos con menos películas públicas y cómo se ordenan.

---

## Punto de partida

MovieLens 32M contiene muchas películas. El resumen raw indica decenas de miles de películas y 32 millones de ratings.

Pero para una demo en un stand no queremos todo.

Queremos:

```text
películas reconocibles
películas actuales o relativamente actuales
películas con suficientes ratings
películas con metadata útil
películas con póster
películas aptas para público joven
```

---

# Fase 1 — Selección de candidatas MovieLens

Script:

```text
build_movielens_32m_candidates.py
```

Parámetros actuales:

```text
--limit 2000
--min-ratings 100
--min-year 2000
--max-tags-per-movie 10
```

Eso significa:

```text
solo candidatas desde el año 2000
solo películas con al menos 100 ratings
máximo 2000 candidatas
```

---

## `dataReliabilityScore`

Mide fiabilidad de datos.

Fórmula conceptual:

```text
0.55 * rating_count_signal
+ 0.30 * average_rating_signal
+ 0.15 * metadata_signal
```

Donde:

```text
rating_count_signal
    ratingCount normalizado respecto al máximo.

average_rating_signal
    averageRating / 5.

metadata_signal
    1.0 si tiene tmdbId e imdbId.
    0.5 si tiene uno de los dos.
    0.0 si no tiene ninguno.
```

---

## `recencyScore`

Mide actualidad.

Reglas:

```text
>= 2020 → 1.0
>= 2015 → 0.9
>= 2010 → 0.8
>= 2000 → 0.7
>= 1995 → 0.55
>= 1990 → 0.45
< 1990  → 0.25
```

Como el filtro actual tiene `min-year=2000`, normalmente veremos mínimo 0.7.

---

## `candidateScore`

Fórmula actual:

```text
0.55 * dataReliabilityScore
+ 0.30 * recencyScore
+ 0.15 * tagAvailabilitySignal
```

Donde:

```text
tagAvailabilitySignal = 1.0 si tiene userTags, si no 0.0
```

Orden de candidatas:

```text
candidateScore desc
recencyScore desc
dataReliabilityScore desc
ratingCount desc
averageRating desc
cleanTitle asc
```

---

# Fase 2 — Enriquecimiento TMDB

Script:

```text
enrich_movielens_32m_with_tmdb.py
```

Aporta:

```text
poster
overview
genres
keywords
cast
directors
certifications
popularity
votes
displayTitle/displayOverview/displayGenres
```

Si falla el enriquecimiento de una película, esa película queda marcada con `enrichmentError`.

---

# Fase 3 — Clasificación de suitability

Script:

```text
build_demo_catalog_from_movielens_32m.py
```

La clasificación produce:

```text
family_friendly_candidate
teen_candidate
adult_or_sensitive
unknown
```

---

## Señales adult/sensitive

Se consideran géneros sensibles:

```text
Horror
Crime
War
Thriller
```

Se consideran keywords sensibles:

```text
murder
serial killer
drug
prison
violence
holocaust
nazi
psychopath
torture
rape
slavery
revenge
gore
```

Certificaciones adultas:

```text
US: R, NC-17
ES: 16, 18
```

Si aparece una señal adulta fuerte, la película puede clasificarse como:

```text
adult_or_sensitive
```

---

## Señales family/teen

Géneros familiares/amigables:

```text
Animation
Family
Adventure
Fantasy
Science Fiction
Comedy
```

Keywords familiares/amigables:

```text
pixar
disney
magic
friendship
superhero
superheroes
school
robot
dinosaur
time travel
alien
wizard
family
fantasy world
```

Certificaciones familiares:

```text
US: G, PG
ES: A, Ai, APTA, 7, TP
```

Certificaciones teen:

```text
US: PG-13
ES: 12
```

---

## Reglas de suitability

Simplificado:

```text
Si certificación adulta → adult_or_sensitive.
Si certificación teen → teen_candidate.
Si certificación familiar → family_friendly_candidate.
Si no hay certificación clara pero hay señales familiares y no adultas → family_friendly_candidate.
Si no hay señales claras → unknown.
```

Si hay señal adulta por géneros/keywords, se añade razón sensible.

---

# Fase 4 — Filtro público

Una película entra en `publicCatalog` solo si:

```text
no tiene enrichmentError
tiene posterPath
ratingCount >= min_ratings
year >= public_min_year
demoSuitability no es adult_or_sensitive ni unknown
si family_only está activo, no puede ser teen_candidate
```

Con parámetros actuales:

```text
min_ratings = 100
public_min_year = 2000
family_only = false
```

Por eso bajamos mucho el número:

```text
de miles de películas posibles
a 2000 candidatas enriquecidas
a 712 públicas
```

---

# Fase 5 — Núcleo colaborativo

Una película entra en `collaborativeCore` si:

```text
no tiene enrichmentError
ratingCount >= min_ratings
year >= collaborative_min_year
```

A diferencia del público, aquí no se excluyen adult_or_sensitive o unknown por sí mismas.

Con parámetros actuales:

```text
collaborative_min_year = 2000
min_ratings = 100
collaborative_core_limit = 2000
```

Resultado actual:

```text
collaborativeCore = 1970
```

---

# Fase 6 — Export offline

Script:

```text
export_offline_dataset_from_movielens_32m.py
```

Transforma el catálogo particionado en tres CSV principales.

---

## `public_movies.csv`

Es exactamente `publicCatalog`.

Orden conservado.

Resultado actual:

```text
712 películas
```

---

## `collaborative_support_movies.csv`

Es:

```text
collaborativeCore - publicCatalog - inválidas técnicas
```

Importante:

```text
No excluye por adult_or_sensitive.
No excluye por unknown.
```

Porque esas películas no se muestran. Solo sirven como soporte colaborativo interno.

Excluye solo si:

```text
movieId inválido
enrichmentError
sin ratings filtrados si hay resumen de ratings
```

Resultado actual:

```text
1258 películas
```

---

## `excluded_movies.csv`

Es lo que no es público ni soporte colaborativo.

Resultado actual:

```text
30 películas
```

Estas son descartes técnicos/no útiles.

---

# Orden del catálogo público

Las películas públicas se ordenan por `_public_sort_key`.

Orden:

```text
standDisplayScore desc
public priority
recencyScore desc
candidateScore desc
dataReliabilityScore desc
ratingCount desc
tmdbPopularity desc
cleanTitle asc
```

---

## `public priority`

Prioridad:

```text
family_friendly_candidate → 0
teen_candidate            → 1
otros                     → 2
```

Pero como `publicCatalog` excluye adult/unknown, normalmente será family o teen.

---

## `standDisplayScore`

Este score intenta ordenar de forma atractiva para el stand.

Fórmula:

```text
0.30 * recencyScore
+ 0.25 * genreAppealSignal
+ 0.20 * tmdbPopularitySignal
+ 0.15 * dataReliabilityScore
+ 0.10 * keywordAppealSignal
- penalty
```

Donde:

```text
recencyScore
    actualidad.

genreAppealSignal
    presencia de géneros atractivos para demo.

tmdbPopularitySignal
    popularidad TMDB normalizada.

dataReliabilityScore
    confianza por ratings/metadata.

keywordAppealSignal
    keywords family/audience-friendly.

penalty
    penalización si es adult_or_sensitive.
```

Aunque adult_or_sensitive no entra en public, el score se calcula para todos durante análisis.

---

## Razones del `standDisplayScore`

Se guardan en `standDisplayReasons`, por ejemplo:

```text
recent_movie
family_animation_or_adventure
teen_friendly_blockbuster
strong_tmdb_popularity
strong_movielens_data
audience_friendly_keywords
adult_signal_penalty
```

Sirven para entender por qué una película subió o bajó en el orden.

---

# Por qué hay tantas menos películas públicas

Porque una película pública debe ser buena para mostrar en un stand:

```text
actual o suficientemente moderna
con suficientes ratings
con póster
con metadata TMDB
no sensible
no unknown
adecuada para público joven
```

No basta con que tenga ratings.

---

# Por qué mantenemos películas sensibles en soporte colaborativo

Porque no se muestran.

Su función es ayudar al modelo colaborativo a entender patrones de usuarios.

Regla fundamental:

```text
El modelo puede usar support para aprender.
La salida final debe limitarse siempre a public_movies.csv.
```

Así podemos aprovechar más ratings sin poner en riesgo la demo.

---

# Relación final de conteos

```text
public_movies.csv                  712
collaborative_support_movies.csv   1258
---------------------------------------
dataset colaborativo útil          1970

excluded_movies.csv                30
```

Ratings útiles:

```text
collaborative_ratings.csv = ratings de public + support = 7.369.524
```


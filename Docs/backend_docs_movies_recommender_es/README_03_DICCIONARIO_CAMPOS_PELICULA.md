# Backend — Diccionario de campos de película

Este documento explica los campos principales que tenemos de cada película.

---

## 1. Identificadores

## `id`

ID que usa la API para identificar la película.

Normalmente coincide con `movieId` de MovieLens.

Uso:

- Identificar la película en frontend.
- Enviar ratings del usuario.
- Evitar duplicados.

---

## `movieId`

ID original de MovieLens.

Uso:

- Relacionar la película con ratings de MovieLens.
- Filtrar ratings.
- Construir recomendador colaborativo.

Importante: los ratings dependen de `movieId`, no del idioma del título.

---

## `movieLensId`

Campo API equivalente a `movieId`.

Uso:

- Exponer explícitamente la procedencia MovieLens.

---

## `tmdbId`

ID de TMDB.

Uso:

- Pedir metadatos a TMDB.
- Relacionar MovieLens con TMDB.
- Obtener póster, overview, géneros, keywords, etc.

---

## `imdbId`

ID de IMDb.

Uso:

- Referencia externa.
- Posibles enlaces o enriquecimiento futuro.

---

# 2. Títulos y descripción

## `title`

Título canónico/interno.

Uso:

- Datos internos.
- Fallback si no existe `displayTitle`.
- Trazabilidad.

---

## `cleanTitle`

Título limpio derivado de MovieLens.

Uso:

- Guardar un título más legible.
- Ordenar.
- Exportar CSVs.

---

## `originalTitle`

Título original.

Uso:

- Trazabilidad.
- Búsqueda.
- No perder el nombre original.

---

## `overview`

Descripción canónica, normalmente en inglés.

Uso:

- Datos internos.
- Fallback si no existe `displayOverview`.
- Futuro recomendador basado en contenido.

---

## `displayTitle`

Título de visualización, normalmente en español.

Uso:

- Cards del frontend.
- Cards de recomendaciones.
- Búsqueda en español.

Si falta, se usa `title`.

---

## `displayOverview`

Descripción de visualización, normalmente en español.

Uso:

- Detalles de película si los mostramos en el futuro.
- Explicaciones visuales.

Si falta, se usa `overview`.

---

# 3. Géneros, keywords y tags

## `genres`

Géneros canónicos, normalmente en inglés.

Ejemplos:

```text
Animation
Adventure
Science Fiction
Family
Comedy
```

Uso:

- Recomendador basado en contenido.
- Heurísticas internas.
- Suitability.
- Fallback de `displayGenres`.

---

## `displayGenres`

Géneros de visualización, normalmente en español.

Ejemplos:

```text
Animación
Aventura
Ciencia ficción
Familia
Comedia
```

Uso:

- UI.
- Filtro/búsqueda por género en español.

---

## `keywords`

Keywords de TMDB.

Normalmente están en inglés.

Ejemplos:

```text
superhero
friendship
space travel
based on comic
```

Uso:

- Señales internas de contenido.
- Futuro buscador inteligente.
- Heurísticas de suitability.

---

## `userTags`

Tags de usuarios de MovieLens.

Ejemplos:

```text
pixar
mind-bending
time travel
superhero
funny
```

Uso:

- Señales de contenido.
- Perfil de gustos.
- Futuro recomendador basado en contenido.

---

## `tags`

Campo de SQLite/API que mezcla keywords de TMDB y userTags de MovieLens, normalizados.

Uso:

- Recomendación placeholder actual.
- Futuro recomendador basado en contenido.

---

# 4. Imágenes

## `posterPath`

Path relativo de TMDB para el póster.

Uso:

- JSON procesado.
- Seed lo transforma en `posterUrl`.

---

## `posterUrl`

URL completa del póster.

Uso:

- Frontend.
- Cards visuales.

---

## `backdropPath`

Path relativo de TMDB para imagen horizontal.

Uso:

- Posibles fondos o pantallas de detalle futuras.

---

## `backdropUrl`

URL completa del backdrop.

Uso:

- Futuras pantallas visuales.

---

# 5. Ratings y calidad

## `ratingCount`

Número de valoraciones en MovieLens.

Uso:

- Medir si una película tiene datos suficientes.
- Construir candidatos.
- Construir collaborative core.

---

## `averageRating`

Media de valoración en MovieLens.

Uso:

- Señal de calidad.
- Revisión manual.
- Ordenación secundaria.

No es la valoración del usuario actual.

---

## `filteredRatingCount`

Aparece en `ml_32m_demo_ratings_by_movie.csv`.

Indica cuántos ratings filtrados quedan para esa película.

Uso:

- Revisar cobertura colaborativa.

---

## `filteredAverageRating`

Media de los ratings filtrados.

Uso:

- Revisión del dataset colaborativo procesado.

---

# 6. Scores internos

## `candidateScore`

Score de la fase de candidatos.

Uso:

- Elegir qué películas pasan a enriquecimiento TMDB.

---

## `dataReliabilityScore`

Score de fiabilidad de datos.

Uso:

- Priorizar películas con suficiente evidencia.

---

## `recencyScore`

Score de recencia.

Uso:

- Priorizar películas modernas.

---

## `standDisplayScore`

Score pensado para ordenar el catálogo público en la demo.

Uso:

- Hacer que las primeras películas sean más atractivas para público joven.
- No es recomendación personalizada.

---

## `standDisplayReasons`

Motivos del `standDisplayScore`.

Ejemplos:

```text
recent_movie
family_animation_or_adventure
strong_tmdb_popularity
strong_movielens_data
```

Uso:

- Debug.
- Revisión manual.

---

# 7. Datos TMDB

## `tmdbPopularity`

Popularidad de TMDB.

Uso:

- Señal de popularidad.
- Ordenación demo.

---

## `tmdbVoteAverage`

Media de votos en TMDB.

Uso:

- Señal secundaria de calidad.

---

## `tmdbVoteCount`

Número de votos en TMDB.

Uso:

- Fiabilidad de `tmdbVoteAverage`.

---

## `runtime`

Duración en minutos.

Uso:

- Revisión.
- Posibles filtros futuros.

---

## `originalLanguage`

Idioma original.

Ejemplos:

```text
en
es
ja
fr
```

---

## `topCast`

Reparto principal.

Uso:

- Revisión.
- Posible buscador futuro.

---

## `directors`

Directores.

Uso:

- Revisión.
- Posible buscador futuro.

---

## `certifications`

Clasificaciones por país.

Ejemplo:

```json
{
  "US": "PG",
  "ES": "7"
}
```

Uso:

- Decidir suitability.
- Evitar contenido sensible.

---

# 8. Suitability y exclusión

## `demoSuitability`

Clasificación interna para la demo.

Valores habituales:

```text
family_friendly_candidate
teen_candidate
adult_or_sensitive
unknown
```

Importante: no es una clasificación oficial, es una heurística.

---

## `suitabilityReasons`

Motivos de la clasificación.

Uso:

- Revisar por qué una película es family/teen/sensitive/unknown.

---

## `publicExclusionReasons`

Motivos por los que una película no entra al catálogo público.

Ejemplos:

```text
missing_poster
below_public_min_year
adult_or_sensitive
unknown_suitability
below_min_ratings
enrichment_error
```

---

# 9. Roles de catálogo

## `catalogRoles`

Lista de roles de una película.

Valores posibles:

```text
public
recommendable
rateable
collaborative_core
excluded_sensitive
```

Uso:

- Saber si se muestra.
- Saber si se puede recomendar.
- Saber si sirve para colaborativo.

---

# 10. Coverage API

## `coverage`

Objeto que devuelve la API con información de cobertura.

Campos:

```text
availableForContent
availableForCollaborative
contentCoverage
collaborativeCoverage
coverageNotes
```

## `availableForContent`

Indica si la película tiene datos suficientes para recomendación basada en contenido.

## `availableForCollaborative`

Indica si la película tiene datos colaborativos.

## `contentCoverage`

Número entre 0 y 1 que resume cobertura de contenido.

## `collaborativeCoverage`

Número entre 0 y 1 que resume cobertura colaborativa.

## `coverageNotes`

Notas explicativas.

---

# 11. Qué campos usar según el caso

## Para mostrar al usuario

```text
displayTitle
displayOverview
displayGenres
posterUrl
year
```

Fallback:

```text
title
overview
genres
```

## Para recomendación basada en contenido

```text
genres
keywords
userTags
tags
overview
ratingCount
averageRating
tmdbPopularity
```

## Para recomendación colaborativa

```text
userId
movieId
rating
timestamp
```

desde:

```text
ml_32m_demo_ratings.csv
```

## Para ordenar el catálogo inicial

```text
standDisplayScore
featured_order
recommendation_order
```

## Para filtrar contenido sensible

```text
demoSuitability
certifications
suitabilityReasons
publicExclusionReasons
```

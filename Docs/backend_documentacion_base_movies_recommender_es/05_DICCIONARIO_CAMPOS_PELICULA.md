# 05 — Diccionario de campos de película

Este documento explica los campos principales de los CSV del dataset offline.

---

# Identificadores

## `movieId`

ID de MovieLens.

Es la clave principal que usamos para relacionar:

```text
películas
ratings
pósters locales
CSV del dataset
```

También se usa como `id` en la API runtime.

---

## `tmdbId`

ID de TMDB.

Sirve para:

- enriquecer metadata;
- rastrear de dónde salió la información TMDB;
- reconstruir metadata si se vuelve a llamar a TMDB.

---

## `imdbId`

ID de IMDb desde MovieLens.

Se guarda como texto porque puede tener ceros a la izquierda.

---

# Títulos

## `title`

Título canónico/original de la fuente.

Puede venir en inglés o con el formato de MovieLens.

Ejemplo:

```text
Spider-Man: Across the Spider-Verse (2023)
```

---

## `cleanTitle`

Título limpio sin año.

Ejemplo:

```text
Spider-Man: Across the Spider-Verse
```

El backend lo usa normalmente como `title` visible canónico si no se usa display.

---

## `originalTitle`

Título original desde TMDB si existe.

---

## `displayTitle`

Título para mostrar al usuario.

Está en español si TMDB lo ofrece.

Ejemplo:

```text
Spider-Man: Cruzando el Multiverso
```

Regla:

```text
Frontend/backend deben preferir displayTitle para mostrar.
```

---

# Año

## `year`

Año extraído del título de MovieLens o metadata.

Se usa para:

- filtrar películas modernas;
- cálculo de recency;
- ordenar/mostrar.

---

# Descripciones

## `overview`

Descripción canónica, normalmente en inglés.

Se puede usar internamente para contenido.

---

## `displayOverview`

Descripción para mostrar al usuario, en español si existe.

---

# Géneros

## `genres`

Géneros canónicos, normalmente en inglés.

Ejemplo:

```text
Animation|Action|Adventure|Science Fiction
```

Se usan para:

- filtrado;
- recomendación basada en contenido;
- heurísticas de suitability;
- búsqueda.

---

## `displayGenres`

Géneros para mostrar al usuario, en español si existe.

Ejemplo:

```text
Animación|Acción|Aventura|Ciencia ficción
```

---

# Keywords y tags

## `keywords`

Keywords de TMDB.

Ejemplo:

```text
superhero|multiverse|based on comic
```

Son señales internas de contenido.

---

## `userTags`

Tags de usuarios de MovieLens.

Ejemplo:

```text
visually appealing|superhero|great soundtrack
```

También son señales internas de contenido.

---

## Diferencia entre `keywords` y `userTags`

```text
keywords
    Vienen de TMDB. Son metadata editorial/comunitaria de TMDB.

userTags
    Vienen de MovieLens. Son etiquetas puestas por usuarios del dataset.
```

Ambas se conservan porque aportan señales distintas.

---

# Personas

## `topCast`

Actores principales, guardados como lista de nombres separada por `|`.

Ejemplo:

```text
Tom Holland|Zendaya|Benedict Cumberbatch
```

Ahora mismo no se muestra de forma principal, pero puede servir en recomendación futura.

---

## `directors`

Directores, también separados por `|`.

Ejemplo:

```text
Christopher Nolan
```

Puede servir para recomendaciones o explicaciones futuras.

---

# Imágenes

## `posterPath`

Path de póster de TMDB.

Ejemplo:

```text
/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg
```

No se usa directamente por frontend en runtime; se usa para descargar el póster local.

---

## `posterFile`

Ruta relativa dentro del dataset offline.

Ejemplo:

```text
images/posters/286897.jpg
```

---

## `posterUrl`

No está necesariamente en el CSV final, pero el backend lo construye.

Ejemplo:

```text
/offline/posters/286897.jpg
```

---

# Runtime y metadata técnica

## `runtime`

Duración en minutos.

---

## `originalLanguage`

Idioma original de la película.

Ejemplo:

```text
en
ja
es
```

---

# Ratings MovieLens

## `ratingCount`

Número de ratings de MovieLens contado en la fase de candidatos/catálogo.

Es una estadística de origen.

---

## `averageRating`

Media MovieLens calculada en la fase de candidatos/catálogo.

---

## `filteredRatingCount`

Número de ratings que realmente quedan en el dataset colaborativo filtrado.

Corresponde al CSV:

```text
offline_dataset/csv/collaborative_ratings.csv
```

---

## `filteredAverageRating`

Media recalculada usando los ratings filtrados.

---

## Diferencia entre `ratingCount` y `filteredRatingCount`

```text
ratingCount
    Conteo original asociado a la película en la fase de candidatos.

filteredRatingCount
    Conteo real dentro del dataset colaborativo que vamos a usar.
```

Ahora suelen coincidir o ser muy parecidos porque el filtrado es por película. En el futuro podrían diferir si filtramos usuarios, fechas, outliers, etc.

---

## Diferencia entre `averageRating` y `filteredAverageRating`

```text
averageRating
    Media original de MovieLens.

filteredAverageRating
    Media real del subconjunto filtrado que usamos.
```

---

# Scores de selección

## `candidateScore`

Score usado para ordenar/seleccionar candidatas desde MovieLens.

Combina:

```text
dataReliabilityScore
recencyScore
tagAvailability
```

---

## `dataReliabilityScore`

Score de fiabilidad de datos.

Tiene en cuenta:

```text
volumen de ratings
averageRating
existencia de tmdbId/imdbId
```

---

## `recencyScore`

Score de actualidad.

La lógica actual:

```text
>= 2020 → 1.0
>= 2015 → 0.9
>= 2010 → 0.8
>= 2000 → 0.7
>= 1995 → 0.55
>= 1990 → 0.45
< 1990  → 0.25
```

---

# Señales TMDB

## `tmdbPopularity`

Popularidad TMDB.

Es útil como señal de reconocimiento/actualidad social, pero no debe dominar por sí sola.

---

## `tmdbVoteAverage`

Media de votos en TMDB.

---

## `tmdbVoteCount`

Número de votos en TMDB.

---

# Suitability y demo

## `demoSuitability`

Clasificación heurística para la demo.

Valores:

```text
family_friendly_candidate
teen_candidate
adult_or_sensitive
unknown
```

---

## `suitabilityReasons`

Razones por las que se clasificó así.

Ejemplo:

```text
Certification indicates family-friendly suitability
Genre or keyword signal indicates sensitive themes
```

---

## `publicExclusionReasons`

Razones por las que una película no puede entrar en catálogo público.

Ejemplos:

```text
missing_poster
below_min_ratings
below_public_min_year
adult_or_sensitive
unknown_suitability
enrichment_error
```

---

## `standDisplayScore`

Score para ordenar películas públicas en la demo/stand.

No es una nota de calidad absoluta. Es una señal de conveniencia para que salgan primero películas:

- actuales;
- reconocibles;
- con géneros atractivos;
- con buena metadata;
- con señales family/teen adecuadas.

---

# Roles de dataset

## `datasetRole`

Aparece en `movie_ratings_summary.csv`.

Valores:

```text
public
collaborative_support
```

`public` significa que la película está en el catálogo visible.

`collaborative_support` significa que no se muestra, pero puede usarse internamente para colaborativo.

---

# Excluded

## `exclusionCategory`

Categoría principal de descarte.

Valores actuales:

```text
missing_or_invalid_movie_id
enrichment_error
missing_filtered_ratings
not_public_or_collaborative_support
```

---

## `exclusionReasons`

Lista de razones técnicas de exclusión.

---


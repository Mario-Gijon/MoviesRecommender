# 04 — Dataset offline

El dataset offline es el resultado final que usa la app en runtime.

Ruta:

```text
Backend/app/data/offline_dataset/
```

Estructura:

```text
offline_dataset/
├── manifest.json
├── csv/
│   ├── public_movies.csv
│   ├── collaborative_support_movies.csv
│   ├── excluded_movies.csv
│   ├── movie_ratings_summary.csv
│   └── collaborative_ratings.csv
└── images/
    └── posters/
        └── {movieId}.jpg
```

---

## Conteos actuales validados

```text
public_movies.csv: 712
collaborative_support_movies.csv: 1258
excluded_movies.csv: 30
movie_ratings_summary.csv: 1970
collaborative_ratings.csv: 7.369.524
posters públicos: 712
```

Además se validó que no hay solapes:

```text
public ∩ support = 0
public ∩ excluded = 0
support ∩ excluded = 0
```

---

# `manifest.json`

Es un JSON pequeño de metadatos.

No contiene películas.

Contiene información como:

```text
datasetName
schemaVersion
generatedAt
sourceDataset
metadataSource
canonicalLanguage
displayLanguage
listSeparator
counts
files
images
notes
```

Sirve para que cualquier app sepa:

- qué dataset está usando;
- dónde están los CSV;
- dónde están los pósters;
- cuántas películas hay;
- qué separador se usa para listas.

---

# `csv/public_movies.csv`

Contiene las películas públicas.

Estas películas son:

```text
visibles
valorables
recomendables
aptas para salir en frontend
con póster local
```

El backend runtime carga este CSV en memoria.

Importante:

```text
Solo public_movies.csv puede aparecer en la app.
```

---

# `csv/collaborative_support_movies.csv`

Contiene películas internas de soporte colaborativo.

Estas películas:

```text
no se muestran
no se valoran directamente
no se recomiendan directamente
no deben salir en explicaciones visibles
sí pueden usarse para entrenar/apoyar el modelo colaborativo
```

Pueden incluir películas sensibles o unknown, porque nunca se mostrarán. Su utilidad es colaborar en el patrón de usuarios.

Regla de seguridad:

```text
El recomendador puede usar support para calcular perfiles,
pero las candidatas finales siempre deben salir de public_movies.csv.
```

---

# `csv/excluded_movies.csv`

Contiene películas descartadas de verdad.

Son películas que no son públicas ni soporte colaborativo.

Motivos posibles:

```text
enrichment_error
missing_or_invalid_movie_id
missing_filtered_ratings
not_public_or_collaborative_support
```

Ahora mismo son pocas: 30.

---

# `csv/movie_ratings_summary.csv`

Resumen de ratings por película útil del dataset offline.

Contiene una fila por película de:

```text
public + collaborative_support
```

Por eso tiene 1970 filas.

Campos principales:

```text
movieId
title
displayTitle
datasetRole
ratingCount
averageRating
filteredRatingCount
filteredAverageRating
```

Sirve para consultar rápidamente cobertura de ratings sin abrir el CSV gigante de ratings.

---

# `csv/collaborative_ratings.csv`

CSV grande de ratings filtrados.

Columnas:

```text
userId,movieId,rating,timestamp
```

Contiene ratings de:

```text
public_movies + collaborative_support_movies
```

Uso:

- futuro recomendador colaborativo;
- entrenamiento de modelos;
- cálculo de similitudes o factores;
- no se carga para pintar el catálogo público.

---

# `images/posters/`

Contiene imágenes locales:

```text
{movieId}.jpg
```

Ejemplo:

```text
images/posters/286897.jpg
```

El backend monta esta carpeta en:

```text
/offline/posters
```

Por tanto, una película pública puede tener:

```text
posterUrl = /offline/posters/286897.jpg
```

El frontend debe resolver esa URL contra el backend.

---

## Por qué no guardamos backdrops

Ahora mismo las cards solo necesitan póster vertical.

Los backdrops:

- pesan más;
- no se usan en runtime;
- se pueden añadir más adelante si hacemos pantallas tipo hero/detail.

---

## Separador de listas

En los CSV, las columnas que contienen listas usan:

```text
|
```

Ejemplo:

```text
Animation|Adventure|Family
```

Esto se usa en:

```text
genres
displayGenres
keywords
userTags
topCast
directors
suitabilityReasons
publicExclusionReasons
```

---

## Dataset final vs caché

`offline_dataset` es final/runtime.

`pipeline_cache` no es final; es caché para reconstruir.


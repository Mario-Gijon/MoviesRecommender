# 09 — Estado actual y siguiente fase

## Estado actual

El proyecto ya tiene una base de datos offline funcional.

La app runtime usa:

```text
offline_dataset/csv/public_movies.csv
offline_dataset/images/posters/
```

No depende de:

```text
SQLite
TMDB en runtime
MovieLens en runtime
```

---

## Datos disponibles

Tenemos:

```text
712 películas públicas
1258 películas de soporte colaborativo
30 descartes
1970 películas con resumen de ratings
7.369.524 ratings colaborativos
712 pósters locales
```

---

## Qué significa cada grupo

### Públicas

```text
public_movies.csv
```

Son las que puede ver y valorar el usuario.

También son las únicas candidatas finales recomendables.

### Soporte colaborativo

```text
collaborative_support_movies.csv
```

No se muestran nunca.

Sirven para construir perfil/modelo colaborativo con más señales.

### Descartadas

```text
excluded_movies.csv
```

No se muestran ni se usan para soporte.

---

## Qué está pendiente

El recomendador real todavía no está implementado.

Ahora mismo `/recommendations` usa una respuesta placeholder.

---

# Siguiente fase: recomendador

El usuario comentó que quiere empezar por el colaborativo porque parece el más sencillo. Hay que matizar:

```text
El colaborativo puede ser sencillo si hacemos una versión básica.
Pero computacionalmente puede ser más delicado que el content-based si usamos 7M ratings directamente.
```

Lo recomendable es implementarlo en fases.

---

## Recomendador colaborativo v1 propuesto

Entrada:

```text
ratings temporales del usuario en la demo
```

Datos disponibles:

```text
offline_dataset/csv/collaborative_ratings.csv
offline_dataset/csv/public_movies.csv
offline_dataset/csv/collaborative_support_movies.csv
```

Regla de seguridad:

```text
La salida final solo puede contener películas de public_movies.csv.
```

---

## Opción colaborativa sencilla

### Item-based collaborative filtering

Idea:

1. El usuario valora algunas películas públicas.
2. Buscamos usuarios de MovieLens que también valoraron esas películas.
3. Usamos sus valoraciones para puntuar otras películas.
4. Filtramos candidatas finales a `public_movies.csv`.
5. Quitamos películas ya valoradas por el usuario actual.

Ventaja:

- se entiende bien;
- aprovecha ratings reales;
- no requiere modelos complejos.

Riesgo:

- no conviene cargar 7.3M ratings en cada request de forma bruta;
- puede necesitar un índice en memoria o artefacto precomputado.

---

## Artefacto colaborativo compacto futuro

Para runtime rápido, probablemente conviene generar un cache/modelo, por ejemplo:

```text
movie_user_ratings index
item similarity top-N
latent vectors
```

Pero no hace falta decidirlo en esta documentación base.

---

## Recomendador content-based futuro

Usaría:

```text
genres
displayGenres solo para mostrar
keywords
userTags
overview
topCast
directors
tmdbPopularity
ratingCount
```

Puede ser muy explicable:

```text
"Te recomendamos esta película porque comparte fantasía, aventura y superhéroes con las que valoraste bien."
```

---

## Recomendador híbrido futuro

Combinaría:

```text
content score
collaborative score
popularity/quality signal
diversity penalty
```

---

## Prioridades recomendadas

1. Confirmar documentación y dataset.
2. Implementar colaborativo v1 de forma segura.
3. Asegurar que solo recomienda públicas.
4. Añadir explicaciones simples.
5. Después mejorar con content/hybrid.

---

## Regla más importante para el recomendador

```text
Puede usar collaborative_support para calcular.
Nunca puede devolver collaborative_support como recomendación final.
```

---

## Qué no tocar todavía

No tocaría todavía:

```text
nuevas fuentes de datos
streaming/trailers
keywords traducidas
sinónimos
backdrops
SQLite
```

El dataset actual ya es suficiente para empezar el recomendador.


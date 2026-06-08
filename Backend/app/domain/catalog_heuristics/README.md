## Modulos de heuristicas del catalogo

`candidate_scoring.py`
Seleccion inicial de candidatas desde MovieLens antes del enriquecimiento con TMDB. `tmdbId` es un requisito obligatorio de elegibilidad; despues calcula `dataReliabilityScore`, `recencyScore` y `candidateScore` para ordenar solo las candidatas elegibles. `dataReliabilityScore` mide la fiabilidad colaborativa de MovieLens con `ratingCount` y `averageRating`, sin usar `tmdbId` ni `imdbId`, y normaliza `ratingCount` de forma logaritmica para suavizar la cola larga de popularidad. `candidateScore` sigue combinando `dataReliabilityScore`, `recencyScore` y `userTagsSignal`, que ahora es gradual segun el numero de `userTags` representativos y se satura en 20.

`suitability.py`
Clasifica peliculas en `family_friendly`, `teen`, `adult_or_sensitive` o `unknown`.

`filtering.py`
Decide si una pelicula puede entrar en catalogo publico, soporte colaborativo o exclusion.

`scoring.py`
Calcula `standDisplayScore` para ordenar las peliculas visibles del stand/demo.

`ordering.py`
Define el orden final y los desempates para las particiones publicas, de soporte y excluidas.

## CandidateScore vs StandDisplayScore

`candidateScore`
Se usa antes del enriquecimiento con TMDB para decidir que peliculas elegibles de MovieLens entran en el dataset candidato. Ordena candidatas con `tmdbId`, pero no sustituye requisitos de elegibilidad.

`standDisplayScore`
Se usa despues del enriquecimiento con TMDB y de suitability para ordenar las peliculas publicas visibles en el stand.

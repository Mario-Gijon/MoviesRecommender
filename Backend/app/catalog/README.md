## Modulos de heuristicas del catalogo

`candidate_scoring.py`
Seleccion inicial de candidatas desde MovieLens antes del enriquecimiento con TMDB. `tmdbId` es un requisito obligatorio de elegibilidad; despues calcula `dataReliabilityScore`, `recencyScore` y `candidateScore` para ordenar solo las candidatas elegibles. `dataReliabilityScore` mide la fiabilidad colaborativa de MovieLens con `ratingCount` y `averageRating`, sin usar `tmdbId` ni `imdbId`, y normaliza `ratingCount` de forma logaritmica para suavizar la cola larga de popularidad. `candidateScore` sigue combinando `dataReliabilityScore`, `recencyScore` y `userTagsSignal`, que ahora es gradual segun el numero de `userTags` representativos y se satura en 20.

`suitability.py`
Clasifica peliculas en `family_friendly`, `teen`, `adult_or_sensitive` o `unknown`.

`family_friendly`: certificacion oficial familiar, salvo si se detectan generos sensibles. Sin certificacion, tambien puede salir de senales familiares si no hay senales sensibles.
`teen`: certificacion oficial teen. Una certificacion familiar con senal de genero sensible se promociona a `teen`. Los generos sensibles no pasan automaticamente a `adult_or_sensitive` salvo si aparecen `publicBlockedTerms`.
`adult_or_sensitive`: certificacion oficial adulta, `publicBlockedTerms`, o certificacion desconocida con generos sensibles.
`unknown`: certificacion ausente o ambigua, sin suficiente senal familiar y sin una senal sensible clara.

`suitability.py` no decide directamente el CSV final. `filtering.py` usa `suitabilityCategory` y `publicBlockedTerms` para decidir si una pelicula puede entrar en el catalogo publico.

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

## Modulos de heuristicas del catalogo

`candidate_scoring.py`
Seleccion inicial de candidatas desde MovieLens antes del enriquecimiento con TMDB. Calcula `dataReliabilityScore`, `recencyScore` y `candidateScore`.

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
Se usa antes del enriquecimiento con TMDB para decidir que peliculas de MovieLens entran en el dataset candidato.

`standDisplayScore`
Se usa despues del enriquecimiento con TMDB y de suitability para ordenar las peliculas publicas visibles en el stand.

import MoviesGrid from './MoviesGrid'

function RatedMoviesStep({
  ratedMovies,
  ratings,
  onRate,
}) {
  return (
    <div className="review-game-step compact-step">
      <section className="game-catalog-panel review-panel">
        {ratedMovies.length ? (
          <MoviesGrid
            movies={ratedMovies}
            ratings={ratings}
            onRate={onRate}
          />
        ) : (
          <div className="game-state">
            <strong>No hay películas valoradas</strong>
          </div>
        )}
      </section>
    </div>
  )
}

export default RatedMoviesStep

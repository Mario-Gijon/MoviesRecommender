import MoviesGrid from './MoviesGrid'

function RateMoviesStep({
  movies,
  ratings,
  ratedMoviesCount,
  isLoadingMovies,
  movieLoadError,
  onRate,
  onRetryLoadMovies,
}) {
  return (
    <div className="step-panel">
      <div className="step-toolbar">
        <div className="stats-chip">Rated movies: {ratedMoviesCount}</div>
        <p className="helper-text">Rate a few films to shape your temporary taste profile.</p>
      </div>
      <div className="scroll-panel">
        {isLoadingMovies ? (
          <p className="helper-text">Fetching movie cards...</p>
        ) : movieLoadError && movies.length === 0 ? (
          <div className="empty-state">
            <h3>Movies could not be loaded</h3>
            <p className="helper-text">
              The app could not reach the backend catalog. Retry after the backend is available.
            </p>
            <button type="button" className="secondary-button" onClick={onRetryLoadMovies}>
              Retry loading movies
            </button>
          </div>
        ) : (
          <MoviesGrid movies={movies} ratings={ratings} onRate={onRate} />
        )}
      </div>
    </div>
  )
}

export default RateMoviesStep

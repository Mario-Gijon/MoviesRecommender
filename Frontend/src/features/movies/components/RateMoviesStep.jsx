import MoviesGrid from './MoviesGrid'

function RateMoviesStep({ movies, ratings, ratedMoviesCount, isLoadingMovies, onRate }) {
  return (
    <div className="step-panel">
      <div className="step-toolbar">
        <div className="stats-chip">Rated movies: {ratedMoviesCount}</div>
        <p className="helper-text">The grid below has its own scroll area for larger future catalogs.</p>
      </div>
      <div className="scroll-panel">
        {isLoadingMovies ? (
          <p className="helper-text">Fetching movie cards...</p>
        ) : (
          <MoviesGrid movies={movies} ratings={ratings} onRate={onRate} />
        )}
      </div>
    </div>
  )
}

export default RateMoviesStep


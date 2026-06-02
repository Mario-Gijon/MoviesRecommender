import MoviesGrid from './MoviesGrid'

function RateMoviesStep({ movies, ratings, ratedMoviesCount, isLoadingMovies, onRate }) {
  return (
    <div className="step-panel">
      <div className="step-toolbar">
        <div className="stats-chip">Rated movies: {ratedMoviesCount}</div>
        <p className="helper-text">Rate a few films to shape your temporary taste profile.</p>
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

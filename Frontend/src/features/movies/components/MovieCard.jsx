function MovieCard({ movie, rating, onRate }) {
  return (
    <article className="card">
      <div className="poster-placeholder">{movie.title.slice(0, 1)}</div>
      <div className="card-body">
        <div className="card-heading">
          <h3>{movie.title}</h3>
          <span>{movie.year}</span>
        </div>
        <p className="meta">{movie.genres.join(' • ')}</p>
        <p className="availability">
          Content: {movie.coverage.availableForContent ? 'yes' : 'no'} | Collaborative:{' '}
          {movie.coverage.availableForCollaborative ? 'yes' : 'no'}
        </p>
        <div className="rating-row">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              className={value === rating ? 'rating-button active' : 'rating-button'}
              onClick={() => onRate(movie.id, value)}
            >
              {value}
            </button>
          ))}
          {rating ? (
            <button type="button" className="clear-button" onClick={() => onRate(movie.id, null)}>
              Clear
            </button>
          ) : null}
        </div>
      </div>
    </article>
  )
}

export default MovieCard

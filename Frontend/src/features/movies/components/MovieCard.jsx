function MovieCard({ movie, rating, onRate }) {
  const genresPreview = movie.genres.slice(0, 3)
  const overviewPreview = movie.overview
    ? `${movie.overview.slice(0, 120)}${movie.overview.length > 120 ? '…' : ''}`
    : ''

  return (
    <article className="card">
      <div className="movie-poster-frame">
        {movie.posterUrl ? (
          <img className="movie-poster" src={movie.posterUrl} alt={`${movie.title} poster`} />
        ) : (
          <div className="poster-placeholder">{movie.title.slice(0, 1)}</div>
        )}
      </div>
      <div className="card-body">
        <div className="card-heading">
          <h3>{movie.title}</h3>
          <span>{movie.year}</span>
        </div>
        <p className="meta">{genresPreview.join(' • ')}</p>
        {overviewPreview ? <p className="overview-preview">{overviewPreview}</p> : null}
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

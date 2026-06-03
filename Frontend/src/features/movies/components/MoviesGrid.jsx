import MovieCard from './MovieCard'

function MoviesGrid({ movies, ratings, onRate }) {
  return (
    <div className="grid">
      {movies.map((movie, index) => (
        <MovieCard
          key={movie.id}
          movie={movie}
          rating={ratings[movie.id] || null}
          onRate={onRate}
          index={index}
        />
      ))}
    </div>
  )
}

export default MoviesGrid
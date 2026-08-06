import { useState } from 'react'

import MovieCard from './MovieCard'

function MoviesGrid({ movies, ratings, onRate }) {
  const [openMovieId, setOpenMovieId] = useState(null)

  function handleToggleMovie(movieId) {
    setOpenMovieId((currentMovieId) => (currentMovieId === movieId ? null : movieId))
  }

  return (
    <div className="grid">
      {movies.map((movie, index) => (
        <MovieCard
          key={movie.movieId || movie.id}
          movie={movie}
          rating={ratings[movie.movieId || movie.id] || null}
          onRate={onRate}
          index={index}
          isTouchOpen={openMovieId === (movie.movieId || movie.id)}
          onToggleTouch={() => handleToggleMovie(movie.movieId || movie.id)}
        />
      ))}
    </div>
  )
}

export default MoviesGrid

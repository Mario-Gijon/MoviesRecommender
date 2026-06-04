export function getMovieDisplayTitle(movie) {
  return movie.displayTitle || movie.title
}

export function getMovieDisplayOverview(movie) {
  return movie.displayOverview || movie.overview
}

export function getMovieDisplayGenres(movie) {
  return movie.displayGenres?.length ? movie.displayGenres : movie.genres
}

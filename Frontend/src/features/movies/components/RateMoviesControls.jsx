function RateMoviesControls({ catalogSearch, onSearchChange }) {
  return (
    <div className="game-search-row">
      <label className="game-search">
        <span aria-hidden="true">⌕</span>
        <span className="sr-only">Search movies</span>
        <input
          type="search"
          value={catalogSearch}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search movies"
        />
      </label>
    </div>
  )
}

export default RateMoviesControls

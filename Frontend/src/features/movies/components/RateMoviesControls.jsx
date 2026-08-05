function RateMoviesControls({ catalogSearch, onSearchChange }) {
  return (
    <div className="game-search-row">
      <label className="game-search">
        <span aria-hidden="true">⌕</span>
        <span className="sr-only">Buscar películas</span>
        <input
          type="search"
          value={catalogSearch}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Buscar películas"
        />
      </label>
    </div>
  )
}

export default RateMoviesControls

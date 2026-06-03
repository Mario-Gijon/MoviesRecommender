import { useEffect, useRef } from 'react'

import MoviesGrid from './MoviesGrid'

function RateMoviesStep({
  movies,
  ratings,
  ratedMoviesCount,
  catalogSearch,
  selectedGenre,
  genreOptions,
  isCatalogLoading,
  isCatalogLoadingMore,
  catalogTotalItems,
  catalogHasLoaded,
  hasMoreCatalogPages,
  catalogError,
  onRate,
  onSearchChange,
  onGenreChange,
  onLoadMore,
  onRetryLoadMovies,
}) {
  const scrollPanelRef = useRef(null)
  const loadMoreSentinelRef = useRef(null)

  useEffect(() => {
    if (!scrollPanelRef.current || !loadMoreSentinelRef.current || !hasMoreCatalogPages) {
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isCatalogLoading && !isCatalogLoadingMore) {
          onLoadMore()
        }
      },
      {
        root: scrollPanelRef.current,
        rootMargin: '120px 0px',
      },
    )

    observer.observe(loadMoreSentinelRef.current)

    return () => observer.disconnect()
  }, [hasMoreCatalogPages, isCatalogLoading, isCatalogLoadingMore, onLoadMore])

  return (
    <div className="step-panel">
      <div className="step-toolbar">
        <div className="stats-chip">Rated movies: {ratedMoviesCount}</div>
        <p className="helper-text">Rate a few films to shape your temporary taste profile.</p>
      </div>
      <div className="catalog-controls">
        <label className="search-field">
          <span className="sr-only">Search movies</span>
          <input
            type="search"
            value={catalogSearch}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search movies..."
          />
        </label>
        <div className="genre-filter-row">
          <button
            type="button"
            className={selectedGenre ? 'filter-chip' : 'filter-chip active'}
            onClick={() => onGenreChange('')}
          >
            All genres
          </button>
          {genreOptions.map((genre) => (
            <button
              key={genre}
              type="button"
              className={selectedGenre === genre ? 'filter-chip active' : 'filter-chip'}
              onClick={() => onGenreChange(genre)}
            >
              {genre}
            </button>
          ))}
        </div>
      </div>
      <div ref={scrollPanelRef} className="scroll-panel">
        {isCatalogLoading && movies.length === 0 ? (
          <p className="helper-text">Loading movie cards from the public catalog...</p>
        ) : catalogError && movies.length === 0 ? (
          <div className="empty-state">
            <h3>Movies could not be loaded</h3>
            <p className="helper-text">
              The app could not reach the backend catalog. Retry after the backend is available.
            </p>
            <button type="button" className="secondary-button" onClick={onRetryLoadMovies}>
              Retry loading movies
            </button>
          </div>
        ) : movies.length === 0 && catalogHasLoaded ? (
          <div className="empty-state">
            <h3>No movies found</h3>
            <p className="helper-text">Try a different title search or clear the genre filter.</p>
          </div>
        ) : (
          <div className="catalog-results">
            <div className="catalog-summary-row">
              <p className="helper-text">
                Showing {movies.length} of {catalogTotalItems} movies
              </p>
              {catalogError && movies.length > 0 ? (
                <p className="error-text">Could not load more movies. You can try again below.</p>
              ) : null}
            </div>
            <MoviesGrid movies={movies} ratings={ratings} onRate={onRate} />
            <div className="catalog-tail">
              {isCatalogLoadingMore ? (
                <p className="helper-text">Loading more movies...</p>
              ) : hasMoreCatalogPages ? (
                <button type="button" className="secondary-button" onClick={onLoadMore}>
                  Load more movies
                </button>
              ) : (
                <p className="helper-text">End of catalog</p>
              )}
              <div ref={loadMoreSentinelRef} className="catalog-sentinel" aria-hidden="true" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default RateMoviesStep

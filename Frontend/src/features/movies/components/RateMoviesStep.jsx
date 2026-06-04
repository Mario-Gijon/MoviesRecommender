import { useEffect, useRef } from 'react'

import useSmoothWheelScroll from '../../../shared/hooks/useSmoothWheelScroll'
import MoviesGrid from './MoviesGrid'

function RateMoviesStep({
  movies,
  ratings,
  ratedMoviesCount,
  catalogSearch,
  isCatalogLoading,
  isCatalogLoadingMore,
  catalogHasLoaded,
  hasMoreCatalogPages,
  catalogError,
  onRate,
  onSearchChange,
  onLoadMore,
  onRetryLoadMovies,
}) {
  const scrollPanelRef = useRef(null)
  const loadMoreSentinelRef = useRef(null)

  useSmoothWheelScroll(scrollPanelRef)

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
        rootMargin: '220px 0px',
      },
    )

    observer.observe(loadMoreSentinelRef.current)

    return () => observer.disconnect()
  }, [hasMoreCatalogPages, isCatalogLoading, isCatalogLoadingMore, onLoadMore])

  return (
    <div className="rate-game-step">
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

        <div className="rated-counter" aria-label={`${ratedMoviesCount} rated movies`}>
          <strong>{ratedMoviesCount}</strong>
          <span>rated</span>
        </div>
      </div>

      <div ref={scrollPanelRef} className="game-catalog-panel">
        {isCatalogLoading && movies.length === 0 ? (
          <div className="game-state">
            <span className="game-loader" aria-hidden="true" />
            <strong>Loading</strong>
          </div>
        ) : catalogError && movies.length === 0 ? (
          <div className="game-state">
            <strong>Catalog unavailable</strong>
            <button type="button" className="game-nav-button primary" onClick={onRetryLoadMovies}>
              Retry
            </button>
          </div>
        ) : movies.length === 0 && catalogHasLoaded ? (
          <div className="game-state">
            <strong>No movies found</strong>
          </div>
        ) : (
          <>
            <MoviesGrid movies={movies} ratings={ratings} onRate={onRate} />

            <div className="game-catalog-tail">
              {isCatalogLoadingMore ? (
                <span className="game-loader small" aria-hidden="true" />
              ) : hasMoreCatalogPages ? (
                <button type="button" className="load-trigger-button" onClick={onLoadMore}>
                  Load more
                </button>
              ) : null}

              <div ref={loadMoreSentinelRef} className="catalog-sentinel" aria-hidden="true" />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default RateMoviesStep
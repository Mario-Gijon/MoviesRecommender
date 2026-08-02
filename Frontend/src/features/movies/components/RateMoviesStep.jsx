import { useEffect, useRef } from 'react'

import { useAppScrollContainer } from '../../../shared/scroll/scrollContext'
import MoviesGrid from './MoviesGrid'

function RateMoviesStep({
  movies,
  ratings,
  isCatalogLoading,
  isCatalogLoadingMore,
  catalogHasLoaded,
  hasMoreCatalogPages,
  catalogError,
  onRate,
  onLoadMore,
  onRetryLoadMovies,
}) {
  const scrollContainerRef = useAppScrollContainer()
  const loadMoreSentinelRef = useRef(null)

  useEffect(() => {
    if (!loadMoreSentinelRef.current || !hasMoreCatalogPages) {
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isCatalogLoading && !isCatalogLoadingMore) {
          onLoadMore()
        }
      },
      {
        root: scrollContainerRef?.current || null,
        rootMargin: '220px 0px',
      },
    )

    observer.observe(loadMoreSentinelRef.current)

    return () => observer.disconnect()
  }, [hasMoreCatalogPages, isCatalogLoading, isCatalogLoadingMore, onLoadMore, scrollContainerRef])

  return (
    <div className="rate-game-step">
      <div className="game-catalog-panel">
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

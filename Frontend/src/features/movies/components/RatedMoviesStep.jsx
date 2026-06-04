import { useRef } from 'react'

import useSmoothWheelScroll from '../../../shared/hooks/useSmoothWheelScroll'
import MoviesGrid from './MoviesGrid'

function RatedMoviesStep({ ratedMovies, ratings, onRate }) {
  const scrollPanelRef = useRef(null)

  useSmoothWheelScroll(scrollPanelRef)

  return (
    <div className="review-game-step compact-step">
      <section ref={scrollPanelRef} className="game-catalog-panel review-panel">
        {ratedMovies.length ? (
          <MoviesGrid movies={ratedMovies} ratings={ratings} onRate={onRate} />
        ) : (
          <div className="game-state">
            <strong>No rated movies yet</strong>
          </div>
        )}
      </section>
    </div>
  )
}

export default RatedMoviesStep
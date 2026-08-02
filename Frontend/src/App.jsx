import { useEffect, useMemo, useRef, useState } from 'react'

import { fetchPublicCatalogPage } from './features/movies/movies.api'
import RateMoviesStep from './features/movies/components/RateMoviesStep'
import RatedMoviesStep from './features/movies/components/RatedMoviesStep'
import RecommendationsStep from './features/recommendations/components/RecommendationsStep'
import {
  createRecommendationRequestId,
  requestRecommendations,
} from './features/recommendations/recommendations.api'
import { resolveAlgorithmForStrategy } from './features/recommendations/strategies'
import AppLayout from './shared/components/AppLayout'
import StepNavigation from './shared/components/StepNavigation'
import StepShell from './shared/components/StepShell'

const STEPS = [
  {
    id: 1,
    title: 'Rate movies',
    description: 'Build your taste profile',
  },
  {
    id: 2,
    title: 'Review profile',
    description: 'Check your ratings',
  },
  {
    id: 3,
    title: 'Recommend',
    description: 'Get your movie picks',
  },
]

const CATALOG_PAGE_SIZE = 40

function App() {
  const [activeStep, setActiveStep] = useState(1)
  const [movies, setMovies] = useState([])
  const [movieIndex, setMovieIndex] = useState({})
  const [catalogPage, setCatalogPage] = useState(1)
  const [catalogPageSize] = useState(CATALOG_PAGE_SIZE)
  const [catalogTotalPages, setCatalogTotalPages] = useState(0)
  const [catalogSearch, setCatalogSearch] = useState('')
  const [debouncedCatalogSearch, setDebouncedCatalogSearch] = useState('')
  const [ratings, setRatings] = useState({})
  const [selectedStrategy, setSelectedStrategy] = useState('content')
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('tfidf')
  const [selectedCollaborativeAlgorithm, setSelectedCollaborativeAlgorithm] = useState('item_knn')
  const [recommendations, setRecommendations] = useState(null)
  const [isCatalogLoading, setIsCatalogLoading] = useState(true)
  const [isCatalogLoadingMore, setIsCatalogLoadingMore] = useState(false)
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false)
  const [catalogError, setCatalogError] = useState('')
  const [recommendationError, setRecommendationError] = useState(null)
  const catalogRequestIdRef = useRef(0)

  async function loadCatalogPage({ page, append, search }) {
    const requestId = catalogRequestIdRef.current + 1
    catalogRequestIdRef.current = requestId

    if (append) {
      setIsCatalogLoadingMore(true)
      setCatalogError('')
    } else {
      setIsCatalogLoading(true)
      setCatalogError('')
      setMovies([])
    }

    try {
      const response = await fetchPublicCatalogPage({
        page,
        pageSize: catalogPageSize,
        search,
        genre: '',
      })

      if (requestId !== catalogRequestIdRef.current) {
        return
      }

      setMovies((currentMovies) => {
        if (!append) {
          return response.items
        }

        const nextMovies = [...currentMovies]
        const seenMovieIds = new Set(currentMovies.map((movie) => movie.id))

        response.items.forEach((movie) => {
          if (!seenMovieIds.has(movie.id)) {
            seenMovieIds.add(movie.id)
            nextMovies.push(movie)
          }
        })

        return nextMovies
      })

      setMovieIndex((currentIndex) => {
        const nextIndex = { ...currentIndex }

        response.items.forEach((movie) => {
          nextIndex[movie.id] = movie
        })

        return nextIndex
      })

      setCatalogPage(response.page)
      setCatalogTotalPages(response.totalPages)
      setCatalogError('')
    } catch {
      if (requestId !== catalogRequestIdRef.current) {
        return
      }

      if (!append) {
        setMovies([])
      }

      setCatalogError('Catalog unavailable')
    } finally {
      if (requestId !== catalogRequestIdRef.current) {
        // eslint-disable-next-line no-unsafe-finally
        return
      }

      setIsCatalogLoading(false)
      setIsCatalogLoadingMore(false)
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedCatalogSearch(catalogSearch.trim())
    }, 300)

    return () => window.clearTimeout(timeoutId)
  }, [catalogSearch])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCatalogPage({
      page: 1,
      append: false,
      search: debouncedCatalogSearch,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedCatalogSearch])

  function handleRetryLoadMovies() {
    loadCatalogPage({
      page: 1,
      append: false,
      search: debouncedCatalogSearch,
    })
  }

  function handleLoadMoreMovies() {
    if (
      isCatalogLoading ||
      isCatalogLoadingMore ||
      catalogPage >= catalogTotalPages
    ) {
      return
    }

    loadCatalogPage({
      page: catalogPage + 1,
      append: true,
      search: debouncedCatalogSearch,
    })
  }

  function handleRate(movieId, rating) {
    setRatings((currentRatings) => {
      const nextRatings = { ...currentRatings }

      if (rating === null) {
        delete nextRatings[movieId]
      } else {
        nextRatings[movieId] = rating
      }

      return nextRatings
    })
  }

  function handleSelectStrategy(strategy) {
    setSelectedStrategy(strategy)
    setSelectedAlgorithm(
      strategy === 'content'
        ? resolveAlgorithmForStrategy(strategy, 'tfidf')
        : selectedCollaborativeAlgorithm,
    )
    setRecommendations(null)
    setRecommendationError(null)
  }

  function handleSelectAlgorithm(algorithm) {
    setSelectedAlgorithm(algorithm)
    if (selectedStrategy === 'collaborative') {
      setSelectedCollaborativeAlgorithm(algorithm)
    }
    setRecommendations(null)
    setRecommendationError(null)
  }

  function handleNextStep() {
    setActiveStep((currentStep) => Math.min(currentStep + 1, STEPS.length))
  }

  function handlePreviousStep() {
    setActiveStep((currentStep) => Math.max(currentStep - 1, 1))
  }

  async function handleGenerateRecommendations() {
    try {
      setIsLoadingRecommendations(true)
      setRecommendationError(null)

      const response = await requestRecommendations({
        requestId: createRecommendationRequestId(),
        strategy: selectedStrategy,
        algorithm: selectedAlgorithm,
        ratings: Object.entries(ratings).map(([movieId, rating]) => ({
          movieId: Number(movieId),
          rating,
        })),
        limit: 10,
      })

      setRecommendations(response)
    } catch (error) {
      setRecommendationError(
        error instanceof Error
          ? error
          : new Error('Could not generate recommendations.'),
      )
    } finally {
      setIsLoadingRecommendations(false)
    }
  }

  const ratedMovies = useMemo(
    () =>
      Object.entries(ratings)
        .map(([movieId, rating]) => {
          const movie = movieIndex[Number(movieId)]
          return movie ? { ...movie, rating } : null
        })
        .filter(Boolean),
    [movieIndex, ratings],
  )

  const ratedMoviesCount = ratedMovies.length
  const hasMoreCatalogPages = catalogPage < catalogTotalPages
  const canGoBack = activeStep > 1
  const canGoNext = activeStep < STEPS.length
  const nextButtonLabel = activeStep === 2 ? 'Recommend' : 'Continue'
  const stepErrorMessage = activeStep === 1 && movies.length === 0
    ? catalogError
    : activeStep === 3
      ? recommendationError?.message || ''
      : ''

  return (
    <AppLayout activeStep={activeStep} steps={STEPS} onStepSelect={setActiveStep}>
      <StepShell errorMessage={stepErrorMessage}>
        {activeStep === 1 ? (
          <RateMoviesStep
            movies={movies}
            ratings={ratings}
            ratedMoviesCount={ratedMoviesCount}
            catalogSearch={catalogSearch}
            isCatalogLoading={isCatalogLoading}
            isCatalogLoadingMore={isCatalogLoadingMore}
            catalogHasLoaded={catalogPage > 0 || movies.length > 0}
            hasMoreCatalogPages={hasMoreCatalogPages}
            catalogError={catalogError}
            onRate={handleRate}
            onSearchChange={setCatalogSearch}
            onLoadMore={handleLoadMoreMovies}
            onRetryLoadMovies={handleRetryLoadMovies}
          />
        ) : null}

        {activeStep === 2 ? (
          <RatedMoviesStep
            ratedMovies={ratedMovies}
            ratings={ratings}
            profileChips={[]}
            onRate={handleRate}
          />
        ) : null}

        {activeStep === 3 ? (
          <RecommendationsStep
            selectedStrategy={selectedStrategy}
            onSelectStrategy={handleSelectStrategy}
            selectedAlgorithm={selectedAlgorithm}
            onSelectAlgorithm={handleSelectAlgorithm}
            onGenerateRecommendations={handleGenerateRecommendations}
            recommendations={recommendations}
            isLoadingRecommendations={isLoadingRecommendations}
            ratedMoviesCount={ratedMoviesCount}
          />
        ) : null}
      </StepShell>

      <StepNavigation
        canGoBack={canGoBack}
        canGoNext={canGoNext}
        nextButtonLabel={nextButtonLabel}
        onBack={handlePreviousStep}
        onNext={handleNextStep}
      />
    </AppLayout>
  )
}

export default App

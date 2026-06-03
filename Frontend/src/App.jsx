import { useEffect, useMemo, useRef, useState } from 'react'

import { fetchPublicCatalogPage } from './features/movies/movies.api'
import RateMoviesStep from './features/movies/components/RateMoviesStep'
import RatedMoviesStep from './features/movies/components/RatedMoviesStep'
import RecommendationsStep from './features/recommendations/components/RecommendationsStep'
import { requestRecommendations } from './features/recommendations/recommendations.api'
import AppLayout from './shared/components/AppLayout'
import StepNavigation from './shared/components/StepNavigation'
import StepShell from './shared/components/StepShell'

const STEPS = [
  {
    id: 1,
    eyebrow: 'Step 1',
    title: 'Rate movies',
    description: 'Rate a few known movies to build a temporary taste profile.',
  },
  {
    id: 2,
    eyebrow: 'Step 2',
    title: 'Review rated movies and detected profile',
    description: 'Review your ratings and see a first simple profile preview.',
  },
  {
    id: 3,
    eyebrow: 'Step 3',
    title: 'Choose strategy and generate recommendations',
    description: 'Choose a strategy and inspect why each movie was recommended.',
  },
]

const PLACEHOLDER_PROFILE_CHIPS = ['Fantasy', 'Adventure', 'Comedy']
const CATALOG_PAGE_SIZE = 40
const GENRE_OPTIONS = [
  'Animation',
  'Adventure',
  'Family',
  'Fantasy',
  'Comedy',
  'Science Fiction',
  'Action',
]

function App() {
  const [activeStep, setActiveStep] = useState(1)
  const [movies, setMovies] = useState([])
  const [movieIndex, setMovieIndex] = useState({})
  const [catalogPage, setCatalogPage] = useState(1)
  const [catalogPageSize] = useState(CATALOG_PAGE_SIZE)
  const [catalogTotalPages, setCatalogTotalPages] = useState(0)
  const [catalogTotalItems, setCatalogTotalItems] = useState(0)
  const [catalogSearch, setCatalogSearch] = useState('')
  const [catalogGenre, setCatalogGenre] = useState('')
  const [debouncedCatalogSearch, setDebouncedCatalogSearch] = useState('')
  const [ratings, setRatings] = useState({})
  const [selectedStrategy, setSelectedStrategy] = useState('hybrid')
  const [recommendations, setRecommendations] = useState(null)
  const [isCatalogLoading, setIsCatalogLoading] = useState(true)
  const [isCatalogLoadingMore, setIsCatalogLoadingMore] = useState(false)
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false)
  const [catalogError, setCatalogError] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const catalogRequestIdRef = useRef(0)

  async function loadCatalogPage({ page, append, search, genre }) {
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
        genre,
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
      setCatalogTotalItems(response.totalItems)
      setCatalogError('')
    } catch {
      if (requestId !== catalogRequestIdRef.current) {
        return
      }

      if (!append) {
        setMovies([])
      }

      setCatalogError(
        append
          ? 'Could not load more movies from the public catalog.'
          : 'Could not load the public catalog. Check that the backend is running and the catalog is available.',
      )
    } finally {
      if (requestId !== catalogRequestIdRef.current) {
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
    loadCatalogPage({
      page: 1,
      append: false,
      search: debouncedCatalogSearch,
      genre: catalogGenre,
    })
  }, [debouncedCatalogSearch, catalogGenre])

  function handleRetryLoadMovies() {
    loadCatalogPage({
      page: 1,
      append: false,
      search: debouncedCatalogSearch,
      genre: catalogGenre,
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
      genre: catalogGenre,
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

  function handleNextStep() {
    setActiveStep((currentStep) => Math.min(currentStep + 1, STEPS.length))
  }

  function handlePreviousStep() {
    setActiveStep((currentStep) => Math.max(currentStep - 1, 1))
  }

  async function handleGenerateRecommendations() {
    try {
      setIsLoadingRecommendations(true)
      setErrorMessage('')
      const response = await requestRecommendations({
        strategy: selectedStrategy,
        ratings: Object.entries(ratings).map(([movieId, rating]) => ({
          movieId: Number(movieId),
          rating,
        })),
      })
      setRecommendations(response)
    } catch {
      setErrorMessage('Could not generate recommendations from the backend.')
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

  const activeStepMeta = STEPS[activeStep - 1]
  const ratedMoviesCount = ratedMovies.length
  const nextButtonLabel = activeStep === STEPS.length ? 'Stay here' : 'Next'
  const canGoBack = activeStep > 1
  const canGoNext = activeStep < STEPS.length
  const statusLabel = isCatalogLoading && movies.length === 0
    ? 'Loading public catalog...'
    : catalogError && movies.length === 0
      ? 'Backend unavailable or catalog not loaded'
      : 'Connected to local public catalog'
  const stepErrorMessage = activeStep === 1 && movies.length === 0 ? catalogError : activeStep === 3 ? errorMessage : ''
  const hasMoreCatalogPages = catalogPage < catalogTotalPages

  return (
    <AppLayout
      activeStep={activeStep}
      steps={STEPS}
      statusLabel={statusLabel}
    >
      <StepShell
        eyebrow={activeStepMeta.eyebrow}
        title={activeStepMeta.title}
        description={activeStepMeta.description}
        errorMessage={stepErrorMessage}
      >
        {activeStep === 1 ? (
          <RateMoviesStep
            movies={movies}
            ratings={ratings}
            ratedMoviesCount={ratedMoviesCount}
            catalogSearch={catalogSearch}
            selectedGenre={catalogGenre}
            genreOptions={GENRE_OPTIONS}
            isCatalogLoading={isCatalogLoading}
            isCatalogLoadingMore={isCatalogLoadingMore}
            catalogTotalItems={catalogTotalItems}
            catalogHasLoaded={catalogPage > 0 || movies.length > 0}
            hasMoreCatalogPages={hasMoreCatalogPages}
            catalogError={catalogError}
            onRate={handleRate}
            onSearchChange={setCatalogSearch}
            onGenreChange={setCatalogGenre}
            onLoadMore={handleLoadMoreMovies}
            onRetryLoadMovies={handleRetryLoadMovies}
          />
        ) : null}

        {activeStep === 2 ? (
          <RatedMoviesStep
            ratedMovies={ratedMovies}
            ratings={ratings}
            profileChips={PLACEHOLDER_PROFILE_CHIPS}
            onRate={handleRate}
          />
        ) : null}

        {activeStep === 3 ? (
          <RecommendationsStep
            selectedStrategy={selectedStrategy}
            onSelectStrategy={setSelectedStrategy}
            onGenerateRecommendations={handleGenerateRecommendations}
            recommendations={recommendations}
            isLoadingRecommendations={isLoadingRecommendations}
            ratedMoviesCount={ratedMoviesCount}
          />
        ) : null}
      </StepShell>

      <StepNavigation
        activeStep={activeStep}
        totalSteps={STEPS.length}
        canGoBack={canGoBack}
        canGoNext={canGoNext}
        nextButtonLabel={nextButtonLabel}
        onBack={handlePreviousStep}
        onNext={handleNextStep}
        hint={
          activeStep === 1 && ratedMoviesCount < 5
            ? 'Tip: rating at least 5 movies gives the demo a clearer profile.'
            : activeStep === 2 && ratedMoviesCount === 0
              ? 'Go back and add a few ratings before moving to recommendations.'
              : ''
        }
      />
    </AppLayout>
  )
}

export default App

import { useEffect, useMemo, useState } from 'react'

import { fetchFeaturedMovies } from './features/movies/movies.api'
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

function App() {
  const [activeStep, setActiveStep] = useState(1)
  const [movies, setMovies] = useState([])
  const [ratings, setRatings] = useState({})
  const [selectedStrategy, setSelectedStrategy] = useState('hybrid')
  const [recommendations, setRecommendations] = useState(null)
  const [isLoadingMovies, setIsLoadingMovies] = useState(true)
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  async function loadMovies() {
    try {
      setIsLoadingMovies(true)
      setErrorMessage('')
      const featuredMovies = await fetchFeaturedMovies()
      setMovies(featuredMovies)
    } catch {
      setMovies([])
      setErrorMessage('Could not load featured movies. Check that the backend is running and the catalog is available.')
    } finally {
      setIsLoadingMovies(false)
    }
  }

  useEffect(() => {
    loadMovies()
  }, [])

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
      movies
        .filter((movie) => ratings[movie.id])
        .map((movie) => ({ ...movie, rating: ratings[movie.id] })),
    [movies, ratings],
  )

  const activeStepMeta = STEPS[activeStep - 1]
  const ratedMoviesCount = ratedMovies.length
  const nextButtonLabel = activeStep === STEPS.length ? 'Stay here' : 'Next'
  const canGoBack = activeStep > 1
  const canGoNext = activeStep < STEPS.length
  const statusLabel = isLoadingMovies
    ? 'Loading featured movies...'
    : errorMessage && movies.length === 0
      ? 'Backend unavailable or catalog not loaded'
      : 'Connected to local catalog'
  const stepErrorMessage = activeStep === 1 && movies.length === 0 ? errorMessage : activeStep === 3 ? errorMessage : ''

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
            isLoadingMovies={isLoadingMovies}
            movieLoadError={movies.length === 0 ? errorMessage : ''}
            onRate={handleRate}
            onRetryLoadMovies={loadMovies}
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

import { RECOMMENDER_OPTIONS } from '../recommendations/strategies'

export const SESSION_KEY = 'sinbad2.moviesRecommender.session.v1'
export const SESSION_VERSION = 1
export const DEFAULT_STRATEGY = 'content'
export const DEFAULT_COLLABORATIVE_ALGORITHM = 'item_knn'

const ALGORITHMS = Object.values(RECOMMENDER_OPTIONS).flat().map((option) => option.value)

export function createDefaultSession() {
  return {
    version: SESSION_VERSION,
    ratings: {},
    ratedMovieSnapshots: {},
    selectedStrategy: DEFAULT_STRATEGY,
    selectedCollaborativeAlgorithm: DEFAULT_COLLABORATIVE_ALGORITHM,
    recommendationsByAlgorithm: {},
  }
}

export function canonicalMovieId(movie) {
  const value = movie?.movieId ?? movie?.id ?? movie
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

export function normalizeMovieSnapshot(movie) {
  const movieId = canonicalMovieId(movie)
  if (!movieId) return null
  return {
    id: movieId,
    movieId,
    title: stringOrEmpty(movie?.title),
    displayTitle: stringOrEmpty(movie?.displayTitle),
    originalTitle: stringOrEmpty(movie?.originalTitle),
    year: validYear(movie?.year),
    posterUrl: stringOrEmpty(movie?.posterUrl),
  }
}

export function mergeMovieSnapshot(current, movie) {
  const next = normalizeMovieSnapshot(movie)
  if (!next) return current || null
  return Object.fromEntries(
    Object.entries({ ...current, ...next }).map(([key, value]) => [key, value || current?.[key] || '']),
  )
}

export function ratingsFingerprint(ratings) {
  return JSON.stringify(
    Object.entries(ratings)
      .map(([movieId, rating]) => [Number(movieId), Number(rating)])
      .sort(([left], [right]) => left - right),
  )
}

export function validateOrMigrateSession(value) {
  if (!value || typeof value !== 'object' || value.version !== SESSION_VERSION) {
    return createDefaultSession()
  }
  const session = createDefaultSession()
  session.ratings = normalizeRatings(value.ratings)
  session.ratedMovieSnapshots = normalizeSnapshots(value.ratedMovieSnapshots)
  session.selectedStrategy = value.selectedStrategy === 'collaborative' ? 'collaborative' : DEFAULT_STRATEGY
  session.selectedCollaborativeAlgorithm = validCollaborativeAlgorithm(value.selectedCollaborativeAlgorithm)
    ? value.selectedCollaborativeAlgorithm
    : DEFAULT_COLLABORATIVE_ALGORITHM
  session.recommendationsByAlgorithm = normalizeRecommendationCaches(value.recommendationsByAlgorithm)
  return session
}

export function loadSession() {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return createDefaultSession()
    const raw = window.localStorage.getItem(SESSION_KEY)
    return raw ? validateOrMigrateSession(JSON.parse(raw)) : createDefaultSession()
  } catch {
    return createDefaultSession()
  }
}

export function saveSession(session) {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(validateOrMigrateSession(session)))
    }
  } catch {
    // The app remains usable when storage is blocked or full.
  }
}

export function clearSession() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) window.localStorage.removeItem(SESSION_KEY)
  } catch {
    // Clearing local-only state is best effort.
  }
}

function normalizeRatings(value) {
  if (!value || typeof value !== 'object') return {}
  return Object.fromEntries(Object.entries(value).flatMap(([movieId, rating]) => {
    const id = canonicalMovieId(movieId)
    const normalizedRating = Number(rating)
    return id && Number.isInteger(normalizedRating) && normalizedRating >= 1 && normalizedRating <= 5
      ? [[id, normalizedRating]]
      : []
  }))
}

function normalizeSnapshots(value) {
  if (!value || typeof value !== 'object') return {}
  return Object.fromEntries(Object.values(value).flatMap((movie) => {
    const snapshot = normalizeMovieSnapshot(movie)
    return snapshot ? [[snapshot.movieId, snapshot]] : []
  }))
}

function normalizeRecommendationCaches(value) {
  if (!value || typeof value !== 'object') return {}
  return Object.fromEntries(Object.entries(value).flatMap(([algorithm, entry]) => {
    if (!ALGORITHMS.includes(algorithm) || !entry || typeof entry !== 'object' || !Array.isArray(entry.response?.recommendations)) return []
    return [[algorithm, { response: entry.response, ratingsFingerprint: stringOrEmpty(entry.ratingsFingerprint), generatedAt: stringOrEmpty(entry.generatedAt) }]]
  }))
}

function validCollaborativeAlgorithm(algorithm) {
  return RECOMMENDER_OPTIONS.collaborative.some((option) => option.value === algorithm)
}

function stringOrEmpty(value) { return typeof value === 'string' ? value : '' }
function validYear(value) { const year = Number(value); return Number.isInteger(year) && year > 1800 && year < 3000 ? year : '' }

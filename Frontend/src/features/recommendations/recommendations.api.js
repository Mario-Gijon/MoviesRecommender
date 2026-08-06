import { apiRequest } from '../../api/client'
import { isAlgorithmValidForStrategy, isStrategyEnabled } from './strategies'

export class RecommendationRequestError extends Error {
  constructor({ requestId, code, message, details, status }) {
    super(message)
    this.name = 'RecommendationRequestError'
    this.requestId = requestId
    this.code = code
    this.details = details
    this.status = status
  }
}

export function createRecommendationRequestId() {
  if (typeof globalThis.crypto?.randomUUID !== 'function') {
    return undefined
  }

  return `web-${globalThis.crypto.randomUUID()}`
}

export function requestRecommendations({ requestId, strategy, algorithm, ratings, limit }) {
  if (!isStrategyEnabled(strategy)) {
    throw new Error('La estrategia seleccionada todavía no está disponible.')
  }

  if (!isAlgorithmValidForStrategy(strategy, algorithm)) {
    throw new Error('El algoritmo seleccionado no corresponde a la estrategia.')
  }

  return apiRequest('/recommendations', {
    method: 'POST',
    body: JSON.stringify({
      requestId,
      strategy,
      algorithm,
      ratings,
      limit,
    }),
    errorNormalizer: normalizeRecommendationError,
  })
}

function normalizeRecommendationError({ payload, status }) {
  const error = payload && typeof payload === 'object' ? payload.error : null
  return new RecommendationRequestError({
    requestId: payload && typeof payload === 'object' ? payload.requestId : null,
    code: error && typeof error.code === 'string' ? error.code : 'request_failed',
    message:
      error && typeof error.message === 'string'
        ? error.message
        : `La solicitud ha fallado con el estado ${status}`,
    details: error && typeof error.details === 'object' && error.details ? error.details : {},
    status,
  })
}

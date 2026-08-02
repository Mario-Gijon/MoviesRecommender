import { afterEach, beforeEach, expect, test } from 'bun:test'

import {
  SESSION_KEY,
  clearSession,
  createDefaultSession,
  loadSession,
  ratingsFingerprint,
  saveSession,
  validateOrMigrateSession,
} from './session'

let values

beforeEach(() => {
  values = new Map()
  globalThis.window = {
    localStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
  }
})

afterEach(() => {
  delete globalThis.window
})

test('restores ratings, snapshots, selections, and independent recommendation caches', () => {
  const session = createDefaultSession()
  session.ratings = { 1: 4 }
  session.ratedMovieSnapshots = { 1: { id: 1, movieId: 1, title: 'Example' } }
  session.selectedStrategy = 'collaborative'
  session.selectedCollaborativeAlgorithm = 'user_knn'
  session.recommendationsByAlgorithm = {
    tfidf: { response: { recommendations: [] }, ratingsFingerprint: '[]', generatedAt: 'now' },
    user_knn: { response: { recommendations: [] }, ratingsFingerprint: '[[1,4]]', generatedAt: 'now' },
  }
  saveSession(session)

  const restored = loadSession()
  expect(restored.ratings).toEqual({ 1: 4 })
  expect(restored.ratedMovieSnapshots[1]).toMatchObject({ id: 1, movieId: 1, title: 'Example' })
  expect(restored.selectedStrategy).toBe('collaborative')
  expect(restored.selectedCollaborativeAlgorithm).toBe('user_knn')
  expect(Object.keys(restored.recommendationsByAlgorithm).sort()).toEqual(['tfidf', 'user_knn'])
})

test('corrupt and unsupported sessions safely use defaults', () => {
  values.set(SESSION_KEY, '{invalid')
  expect(loadSession()).toEqual(createDefaultSession())
  values.set(SESSION_KEY, JSON.stringify({ version: 99 }))
  expect(loadSession()).toEqual(createDefaultSession())
})

test('invalid saved strategy and algorithm use safe defaults', () => {
  const restored = validateOrMigrateSession({
    version: 1,
    ratings: {},
    ratedMovieSnapshots: {},
    selectedStrategy: 'unknown',
    selectedCollaborativeAlgorithm: 'unknown',
    recommendationsByAlgorithm: {},
  })
  expect(restored.selectedStrategy).toBe('content')
  expect(restored.selectedCollaborativeAlgorithm).toBe('item_knn')
})

test('rating fingerprints are deterministic and clearing removes only the session key', () => {
  expect(ratingsFingerprint({ 42: 5, 1: 4 })).toBe(ratingsFingerprint({ 1: 4, 42: 5 }))
  values.set('another-key', 'kept')
  values.set(SESSION_KEY, 'session')
  clearSession()
  expect(values.has(SESSION_KEY)).toBe(false)
  expect(values.get('another-key')).toBe('kept')
})

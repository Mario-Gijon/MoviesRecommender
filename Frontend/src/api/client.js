const DEFAULT_API_URL = import.meta.env.DEV ? 'http://localhost:8014' : '/api'

const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL

export async function apiRequest(path, options = {}) {
  const { errorNormalizer, ...requestOptions } = options
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...requestOptions,
  })

  if (!response.ok) {
    let payload = null
    try {
      payload = normalizeApiPayload(await response.json())
    } catch {
      // The generic client remains usable for APIs that do not return JSON errors.
    }
    if (errorNormalizer) {
      throw errorNormalizer({ payload, status: response.status })
    }
    throw new Error(`Request failed with status ${response.status}`)
  }

  const payload = await response.json()
  return normalizeApiPayload(payload)
}

export { API_URL }

function normalizeApiPayload(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeApiPayload)
  }

  if (!value || typeof value !== 'object') {
    return value
  }

  const normalizedEntries = Object.entries(value).map(([key, entryValue]) => {
    if (key === 'posterUrl' && typeof entryValue === 'string' && entryValue.startsWith('/')) {
      return [key, normalizeRelativeUrl(entryValue)]
    }

    return [key, normalizeApiPayload(entryValue)]
  })

  return Object.fromEntries(normalizedEntries)
}

function normalizeRelativeUrl(path) {
  if (API_URL.startsWith('http://') || API_URL.startsWith('https://')) {
    return new URL(path, API_URL).toString()
  }

  return path
}

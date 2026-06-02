const DEFAULT_API_URL = 'http://localhost:8014'

const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json()
}

export { API_URL }


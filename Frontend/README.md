# Frontend

React + Vite frontend for the explainable movie recommender demo.

## Run locally

```bash
bun install
bun dev
```

## Environment

The frontend reads `VITE_API_URL` and defaults to `http://localhost:8014`.

## Current scope

- Featured movies are fetched from the local FastAPI backend.
- Ratings are stored only in React state.
- Recommendation results are placeholder deterministic responses for now.


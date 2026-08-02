import { expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'

const styles = readFileSync(new URL('../../styles/global.css', import.meta.url), 'utf8')
const layout = readFileSync(new URL('../components/AppLayout.jsx', import.meta.url), 'utf8')
const app = readFileSync(new URL('../../App.jsx', import.meta.url), 'utf8')
const returnButton = readFileSync(
  new URL('../components/ScrollToSectionTopButton.jsx', import.meta.url),
  'utf8',
)
const rateMoviesStep = readFileSync(
  new URL('../../features/movies/components/RateMoviesStep.jsx', import.meta.url),
  'utf8',
)
const rateMoviesControls = readFileSync(
  new URL('../../features/movies/components/RateMoviesControls.jsx', import.meta.url),
  'utf8',
)
const ratedMoviesControls = readFileSync(
  new URL('../../features/movies/components/RatedMoviesControls.jsx', import.meta.url),
  'utf8',
)
const recommendationControls = readFileSync(
  new URL('../../features/recommendations/components/RecommendationControls.jsx', import.meta.url),
  'utf8',
)
const ratedMoviesStep = readFileSync(
  new URL('../../features/movies/components/RatedMoviesStep.jsx', import.meta.url),
  'utf8',
)
const recommendationsStep = readFileSync(
  new URL('../../features/recommendations/components/RecommendationsStep.jsx', import.meta.url),
  'utf8',
)

test('the shell owns vertical scrolling while catalogue panels remain in document flow', () => {
  expect(styles).toMatch(/\.game-shell\s*\{[^}]*overflow-y:\s*auto/s)
  expect(styles).toMatch(/\.game-catalog-panel,[\s\S]*?overflow:\s*visible/s)
  expect(styles).not.toMatch(/\.game-catalog-panel\s*\{[^}]*overflow-y:\s*auto/s)
})

test('the composite sticky header owns global navigation and active controls', () => {
  expect(styles).toMatch(/\.game-header\s*\{[^}]*grid-template-columns:\s*max-content minmax\(0, 1fr\)/s)
  expect(styles).toMatch(/\.app-sticky-header\s*\{[^}]*position:\s*sticky[^}]*top:\s*0/s)
  expect(styles).toMatch(/\.game-header\s*\{[^}]*position:\s*static/s)
  expect(layout).toContain('className="app-sticky-header"')
  expect(layout).toContain('className="active-section-controls"')
  expect(app).toContain('sectionControls={sectionControls}')
})

test('each active section supplies its controls only through the composite header', () => {
  expect(rateMoviesControls).toContain('className="game-search-row"')
  expect(rateMoviesControls).toContain('className="rated-counter"')
  expect(ratedMoviesControls).toContain('className="review-profile-toolbar"')
  expect(recommendationControls).toContain('className="recommend-toolbar compact-recommend-toolbar"')
  expect(app).toContain('<RateMoviesControls')
  expect(app).toContain('<RatedMoviesControls')
  expect(app).toContain('<RecommendationControls')
  expect(rateMoviesStep).not.toContain('className="game-search-row"')
  expect(ratedMoviesStep).not.toContain('className="review-profile-toolbar"')
  expect(recommendationsStep).not.toContain('className="recommend-toolbar compact-recommend-toolbar"')
})

test('the sticky header has no top scroll gap and the return button starts hidden', () => {
  expect(styles).toMatch(/\.game-shell\s*\{[^}]*padding:\s*0 0 14px/s)
  expect(styles).toMatch(/\.section-top-button\s*\{[^}]*opacity:\s*0/s)
  expect(returnButton).toContain('aria-label="Volver al inicio de la sección"')
})

test('step changes preserve the initial header and then reset to absolute top', () => {
  expect(layout).toContain('const hasMountedRef = useRef(false)')
  expect(layout).toContain('if (!hasMountedRef.current)')
  expect(layout).toContain("scrollToApplicationTop(container, 'auto')")
})

test('catalogue infinite loading observes the shared shell context', () => {
  expect(rateMoviesStep).toContain('useAppScrollContainer')
  expect(rateMoviesStep).toContain('root: scrollContainerRef?.current || null')
  expect(rateMoviesStep).not.toContain('useSmoothWheelScroll')
})

import { getAlgorithmsForStrategy } from '../strategies'

function AlgorithmSelector({ strategy, value, onChange }) {
  return (
    <label className="recommendation-algorithm-selector">
      <span>Algoritmo</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {getAlgorithmsForStrategy(strategy).map((algorithm) => (
          <option key={algorithm.value} value={algorithm.value}>
            {algorithm.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default AlgorithmSelector

import { useEffect, useId, useRef, useState } from 'react'

import { getAlgorithmsForStrategy } from '../strategies'

function AlgorithmSelector({ strategy, value, onChange }) {
  const options = getAlgorithmsForStrategy(strategy)
  const [isOpen, setIsOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    Math.max(0, options.findIndex((option) => option.value === value)),
  )
  const rootRef = useRef(null)
  const listboxId = useId()
  const selectedOption = options.find((option) => option.value === value) || options[0]

  useEffect(() => {
    function handlePointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setIsOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [])

  function selectOption(option) {
    onChange(option.value)
    setIsOpen(false)
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      setIsOpen(false)
      return
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setIsOpen(true)
      setHighlightedIndex((current) => (current + direction + options.length) % options.length)
      return
    }

    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      setIsOpen(true)
      setHighlightedIndex(event.key === 'Home' ? 0 : options.length - 1)
      return
    }

    if ((event.key === 'Enter' || event.key === ' ') && isOpen) {
      event.preventDefault()
      selectOption(options[highlightedIndex])
    }
  }

  return (
    <div ref={rootRef} className="recommendation-algorithm-selector">
      <button
        type="button"
        className="recommendation-algorithm-trigger"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        onClick={() => {
          setHighlightedIndex(Math.max(0, options.findIndex((option) => option.value === value)))
          setIsOpen((current) => !current)
        }}
        onKeyDown={handleKeyDown}
        aria-label={selectedOption?.label}
        title={selectedOption?.label}
      >
        <span className="recommendation-algorithm-label">{selectedOption?.label}</span>
        <span className="recommendation-algorithm-chevron" aria-hidden="true" />
      </button>
      {isOpen ? (
        <div id={listboxId} className="recommendation-algorithm-menu" role="listbox" aria-label="Algoritmo">
          {options.map((option, index) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={option.value === value}
              className={`recommendation-algorithm-option${index === highlightedIndex ? ' highlighted' : ''}${option.value === value ? ' selected' : ''}`}
              onMouseEnter={() => setHighlightedIndex(index)}
              onClick={() => selectOption(option)}
            >
              <span>{option.label}</span>
              {option.value === value ? <span aria-hidden="true">✓</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default AlgorithmSelector

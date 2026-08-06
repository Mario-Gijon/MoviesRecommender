import { createContext, useContext } from 'react'

export const AppScrollContext = createContext(null)

export function useAppScrollContainer() {
  return useContext(AppScrollContext)
}

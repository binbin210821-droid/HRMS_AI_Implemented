import { useEffect, useState } from 'react'

import { getHealth } from '../features/health/healthApi.js'

export function useHealth() {
  const [state, setState] = useState({ data: null, error: null, isLoading: true })

  useEffect(() => {
    let isMounted = true

    getHealth()
      .then((data) => {
        if (isMounted) setState({ data, error: null, isLoading: false })
      })
      .catch((error) => {
        if (isMounted) setState({ data: null, error, isLoading: false })
      })

    return () => {
      isMounted = false
    }
  }, [])

  return state
}

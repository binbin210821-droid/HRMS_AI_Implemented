import { create } from 'zustand'

import { getCurrentUser, logout as requestLogout } from '../features/auth/authApi.js'
import { rotateRequestSession } from '../services/requestCoordinator.js'

let initializationPromise = null

function userState(user, isInitializing = false) {
  return {
    currentUser: user,
    // Giữ alias nội bộ để các màn hình hiện tại không bị ảnh hưởng.
    claims: user,
    role: user?.role || null,
    isAuthenticated: Boolean(user),
    isInitializing,
  }
}

function clearState(isInitializing = false) {
  return {
    currentUser: null,
    claims: null,
    role: null,
    isAuthenticated: false,
    isInitializing,
  }
}

export const useAuthStore = create((set) => ({
  ...clearState(true),
  setUser: (user) => {
    rotateRequestSession()
    set(userState(user))
  },
  // Alias tương thích nội bộ; dữ liệu đầu vào phải là CurrentUser từ backend.
  login: (user) => {
    rotateRequestSession()
    set(userState(user))
  },
  initializeSession: async () => {
    if (initializationPromise) return initializationPromise

    set({ isInitializing: true })
    initializationPromise = getCurrentUser()
      .then((user) => {
        rotateRequestSession()
        set(userState(user))
        return user
      })
      .catch(() => {
        rotateRequestSession()
        set(clearState())
        return null
      })
      .finally(() => {
        initializationPromise = null
      })
    return initializationPromise
  },
  clearSession: () => {
    rotateRequestSession()
    set(clearState())
  },
  logout: () => {
    const request = requestLogout().catch(() => undefined)
    rotateRequestSession()
    set(clearState())
    return request
  },
}))

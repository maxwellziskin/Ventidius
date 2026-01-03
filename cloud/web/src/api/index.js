/**
 * Ziskin Field Systems - API Client
 *
 * Centralized API client for communicating with the backend.
 */

const API_BASE = '/api'

async function fetchWithAuth(url, options = {}) {
  // Get token from Clerk
  const token = await window.Clerk?.session?.getToken()

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || 'Request failed')
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

// Auth
export const getCurrentUser = () => fetchWithAuth('/auth/me')

// Sites
export const getSites = () => fetchWithAuth('/sites')
export const getSite = (id) => fetchWithAuth(`/sites/${id}`)
export const createSite = (data) => fetchWithAuth('/sites', { method: 'POST', body: JSON.stringify(data) })
export const updateSite = (id, data) => fetchWithAuth(`/sites/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteSite = (id) => fetchWithAuth(`/sites/${id}`, { method: 'DELETE' })
export const getSiteCameras = (siteId) => fetchWithAuth(`/sites/${siteId}/cameras`)

// Cameras
export const getCameras = () => fetchWithAuth('/cameras')
export const getCamera = (id) => fetchWithAuth(`/cameras/${id}`)
export const createCamera = (data) => fetchWithAuth('/cameras', { method: 'POST', body: JSON.stringify(data) })
export const updateCamera = (id, data) => fetchWithAuth(`/cameras/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteCamera = (id) => fetchWithAuth(`/cameras/${id}`, { method: 'DELETE' })
export const getStreamUrl = (cameraId) => fetchWithAuth(`/cameras/${cameraId}/stream`)

// PTZ
export const sendPTZCommand = (cameraId, command) =>
  fetchWithAuth(`/ptz/cameras/${cameraId}/ptz`, { method: 'POST', body: JSON.stringify(command) })
export const getPTZPresets = (cameraId) => fetchWithAuth(`/ptz/cameras/${cameraId}/presets`)
export const createPTZPreset = (cameraId, data) =>
  fetchWithAuth(`/ptz/cameras/${cameraId}/presets`, { method: 'POST', body: JSON.stringify(data) })

// Users
export const getUsers = () => fetchWithAuth('/users')
export const getUser = (id) => fetchWithAuth(`/users/${id}`)
export const updateUser = (id, data) => fetchWithAuth(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteUser = (id) => fetchWithAuth(`/users/${id}`, { method: 'DELETE' })
export const inviteUser = (data) => fetchWithAuth('/users/invite', { method: 'POST', body: JSON.stringify(data) })
export const getUserCameras = (userId) => fetchWithAuth(`/users/${userId}/cameras`)
export const updateUserCameras = (userId, permissions) =>
  fetchWithAuth(`/users/${userId}/cameras`, { method: 'PUT', body: JSON.stringify(permissions) })

// Exports
export const getExports = (status) => fetchWithAuth(`/exports${status ? `?status_filter=${status}` : ''}`)
export const getExport = (id) => fetchWithAuth(`/exports/${id}`)
export const createExport = (data) => fetchWithAuth('/exports', { method: 'POST', body: JSON.stringify(data) })
export const cancelExport = (id) => fetchWithAuth(`/exports/${id}`, { method: 'DELETE' })

// Admin
export const getClients = () => fetchWithAuth('/admin/clients')
export const getClient = (id) => fetchWithAuth(`/admin/clients/${id}`)
export const createClient = (data) => fetchWithAuth('/admin/clients', { method: 'POST', body: JSON.stringify(data) })
export const updateClient = (id, data) => fetchWithAuth(`/admin/clients/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteClient = (id) => fetchWithAuth(`/admin/clients/${id}`, { method: 'DELETE' })
export const getSiteHealth = (siteId) => fetchWithAuth(`/admin/sites/${siteId}/health`)
export const rebootSite = (siteId) => fetchWithAuth(`/admin/sites/${siteId}/reboot`, { method: 'POST' })
export const getAuditLogs = (params = {}) => {
  const query = new URLSearchParams(params).toString()
  return fetchWithAuth(`/admin/audit${query ? `?${query}` : ''}`)
}
export const getStats = () => fetchWithAuth('/admin/stats')

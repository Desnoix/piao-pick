import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail || error.message
    console.error('[API Error]', error.config?.url, detail)
    return Promise.reject(error)
  }
)

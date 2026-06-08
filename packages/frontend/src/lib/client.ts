import axios from 'axios'

export const client = axios.create({ baseURL: '/api' })

// Token interceptor — attaches Bearer JWT to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = Bearer +"${token}"
  return config
})

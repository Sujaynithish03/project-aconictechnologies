import { api } from './client'
import type { TokenResponse, User } from '../types'

export async function signup(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/signup', { email, password })
  return data
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/login', { email, password })
  return data
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await api.get<User>('/me')
  return data
}

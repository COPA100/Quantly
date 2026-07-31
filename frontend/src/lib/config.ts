export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export const googleEnabled = Boolean(GOOGLE_CLIENT_ID)

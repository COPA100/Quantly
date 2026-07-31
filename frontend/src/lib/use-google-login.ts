import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { setTokens } from './auth'
import { googleLogin } from './auth-api'

// shared by the login and register pages: exchange a Google ID token for our
// own JWT pair, store it, and land on the dashboard.
export function useGoogleLogin() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (idToken: string) => googleLogin(idToken),
    onSuccess: (tokens) => {
      setTokens(tokens)
      navigate('/')
    },
  })
}

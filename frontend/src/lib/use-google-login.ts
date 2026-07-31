import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { googleLogin } from './auth-api'
import { useAuth } from './auth-context'

// shared by the login and register pages: exchange a Google ID token for our
// own JWT pair, store it, and land on the dashboard.
export function useGoogleLogin() {
  const navigate = useNavigate()
  const auth = useAuth()
  return useMutation({
    mutationFn: (idToken: string) => googleLogin(idToken),
    onSuccess: (tokens) => {
      auth.login(tokens)
      navigate('/')
    },
  })
}

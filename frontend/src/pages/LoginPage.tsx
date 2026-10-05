import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/Button'
import GoogleAuthSection from '../components/GoogleAuthSection'
import TextField from '../components/TextField'
import { errorMessage } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { login } from '../lib/auth-api'

export default function LoginPage() {
  const navigate = useNavigate()
  const auth = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (tokens) => {
      auth.login(tokens)
      navigate('/')
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Sign in to see your portfolios."
      footer={
        <span>
          Don&apos;t have an account?{' '}
          <Link to="/register" className="font-medium text-ink underline decoration-hairline-strong underline-offset-4 hover:decoration-ink">
            Create one
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {mutation.isError && (
          <p className="text-sm text-loss">{errorMessage(mutation.error)}</p>
        )}
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Signing in' : 'Sign in'}
        </Button>
      </form>
      <GoogleAuthSection />
    </AuthLayout>
  )
}

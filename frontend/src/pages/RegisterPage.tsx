import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/Button'
import GoogleAuthSection from '../components/GoogleAuthSection'
import TextField from '../components/TextField'
import { errorMessage } from '../lib/api'
import { setTokens } from '../lib/auth'
import { registerAndLogin } from '../lib/auth-api'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => registerAndLogin(email, password),
    onSuccess: (tokens) => {
      setTokens(tokens)
      navigate('/')
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start analyzing your portfolio"
      footer={
        <span>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:underline">
            Sign in
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
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <p className="text-xs text-slate-500">At least 8 characters.</p>
        {mutation.isError && (
          <p className="text-sm text-red-600">{errorMessage(mutation.error)}</p>
        )}
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
      <GoogleAuthSection />
    </AuthLayout>
  )
}

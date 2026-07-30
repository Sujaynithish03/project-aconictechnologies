import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { toErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'
import { Alert, Icon, Input } from '../components/ui'

export default function Login() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const destination = (location.state as { from?: string } | null)?.from ?? '/dashboard'

  if (isAuthenticated) return <Navigate to={destination} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate(destination, { replace: true })
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not sign in.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-lg">
        <div className="space-y-xs">
          <h1 className="text-headline-lg text-on-surface">Welcome back</h1>
          <p className="text-body-md text-on-surface-variant">
            Sign in to access your AI workspace.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-sm">
          {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}

          <Input
            label="Email Address"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@company.com"
          />

          <Input
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
          />

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-sm flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container py-4 font-semibold text-on-primary-container shadow-lg transition-all hover:bg-primary-container/90 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60"
          >
            <span>{isSubmitting ? 'Signing in…' : 'Log In'}</span>
            {!isSubmitting && <Icon name="arrow_forward" className="text-[20px]" />}
          </button>
        </form>

        <p className="text-center text-body-md text-on-surface-variant">
          Don&apos;t have an account?{' '}
          <Link to="/signup" className="font-semibold text-primary hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}

import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { toErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import AuthLayout from '../components/AuthLayout'
import { Alert, Icon, Input } from '../components/ui'

/** Mirrors the backend password policy so users get feedback before submitting. */
function validatePassword(password: string): string | null {
  if (password.length < 8) return 'Use at least 8 characters.'
  if (!/[a-zA-Z]/.test(password)) return 'Include at least one letter.'
  if (!/\d/.test(password)) return 'Include at least one number.'
  return null
}

export default function Signup() {
  const { signup, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to="/dashboard" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const passwordError = validatePassword(password)
    const confirmError = password !== confirm ? 'Passwords do not match.' : undefined
    if (passwordError || confirmError) {
      setFieldErrors({ password: passwordError ?? undefined, confirm: confirmError })
      return
    }

    setFieldErrors({})
    setIsSubmitting(true)
    try {
      await signup(email.trim(), password)
      navigate('/dashboard', { replace: true })
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not create the account.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-lg">
        <div className="space-y-xs">
          <h1 className="text-headline-lg text-on-surface">Get started</h1>
          <p className="text-body-md text-on-surface-variant">
            Create your account to access the AI workspace.
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
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
            hint="At least 8 characters, with a letter and a number."
            placeholder="••••••••"
          />

          <Input
            label="Confirm Password"
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            error={fieldErrors.confirm}
            placeholder="••••••••"
          />

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-sm flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container py-4 font-semibold text-on-primary-container shadow-lg transition-all hover:bg-primary-container/90 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60"
          >
            <span>{isSubmitting ? 'Creating account…' : 'Sign Up'}</span>
            {!isSubmitting && <Icon name="arrow_forward" className="text-[20px]" />}
          </button>
        </form>

        <p className="text-center text-body-md text-on-surface-variant">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-primary hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}

import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Icon, Spinner } from './ui'

/** Gates authenticated pages, preserving the intended destination. */
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // Wait for the stored token to be validated, or a refresh would bounce a
  // signed-in user to the login page.
  if (isLoading) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-on-primary">
          <Icon name="memory" className="text-2xl" filled />
        </div>
        <Spinner className="h-6 w-6 text-primary" />
        <p className="font-mono text-label-sm uppercase tracking-widest text-outline">
          Restoring session
        </p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}

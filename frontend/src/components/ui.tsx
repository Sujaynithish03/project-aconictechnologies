/** Reusable primitives styled to the CognitiveOS design system. */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'
import type { DocumentStatus } from '../types'

/* -------------------------------------------------------------------------- */
/* Icon — Material Symbols Outlined, as used throughout the design            */
/* -------------------------------------------------------------------------- */

export function Icon({
  name,
  className = '',
  filled = false,
}: {
  name: string
  className?: string
  filled?: boolean
}) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined ${filled ? 'filled' : ''} ${className}`}
    >
      {name}
    </span>
  )
}

/* -------------------------------------------------------------------------- */
/* Button                                                                     */
/* -------------------------------------------------------------------------- */

type ButtonVariant = 'primary' | 'filled' | 'outline' | 'ghost' | 'danger'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  isLoading?: boolean
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  // Light lavender fill — the design's main page-level action.
  primary:
    'bg-primary text-on-primary font-semibold shadow-lg shadow-primary/20 hover:scale-[1.02] active:scale-[0.98]',
  // Deep indigo container — used for submits and the sidebar CTA.
  filled:
    'bg-primary-container text-on-primary-container font-semibold shadow-lg hover:bg-primary-container/90 active:scale-[0.98]',
  outline:
    'border border-outline-variant/30 text-on-surface hover:bg-surface-container-high',
  ghost: 'text-on-surface-variant hover:bg-surface-container-high/50 hover:text-on-surface',
  danger: 'text-error hover:bg-error/10',
}

export function Button({
  variant = 'primary',
  isLoading = false,
  disabled,
  className = '',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-body-md transition-all disabled:pointer-events-none disabled:opacity-50 ${BUTTON_VARIANTS[variant]} ${className}`}
    >
      {isLoading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  )
}

/** Circular icon-only button, as in the top header of the design. */
export function IconButton({
  icon,
  label,
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon: string; label: string }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={`flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-surface-container-high/50 hover:text-on-surface disabled:opacity-40 ${className}`}
    >
      <Icon name={icon} />
    </button>
  )
}

/* -------------------------------------------------------------------------- */
/* Input                                                                      */
/* -------------------------------------------------------------------------- */

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

export function Input({ label, error, hint, id, className = '', ...rest }: InputProps) {
  const inputId = id ?? rest.name ?? label.toLowerCase().replace(/\s+/g, '-')
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined

  return (
    <div className={`space-y-xs ${className}`}>
      <label
        htmlFor={inputId}
        className="ml-1 block text-label-sm font-mono uppercase text-on-surface-variant"
      >
        {label}
      </label>
      <input
        {...rest}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`w-full rounded-xl border bg-white/5 px-4 py-3 text-body-md text-on-surface outline-none transition-all placeholder:text-outline/50 focus:ring-2 ${
          error
            ? 'border-error/60 focus:border-error focus:ring-error/40'
            : 'border-outline-variant/30 focus:border-primary focus:ring-primary/50'
        }`}
      />
      {error ? (
        <p id={`${inputId}-error`} className="ml-1 text-label-sm text-error">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="ml-1 text-label-sm text-outline">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Feedback                                                                   */
/* -------------------------------------------------------------------------- */

export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

export function Alert({
  tone = 'error',
  children,
  onDismiss,
}: {
  tone?: 'error' | 'success' | 'info'
  children: ReactNode
  onDismiss?: () => void
}) {
  const tones = {
    error: 'bg-error-container/20 border-error/30 text-on-error-container',
    success: 'bg-tertiary-container/20 border-tertiary/30 text-on-tertiary-container',
    info: 'bg-primary-container/20 border-primary/30 text-on-primary-container',
  }
  const icons = { error: 'error', success: 'check_circle', info: 'info' }

  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-body-md ${tones[tone]}`}
    >
      <Icon name={icons[tone]} className="mt-0.5 shrink-0 text-[20px]" />
      <span className="min-w-0 flex-1 break-words">{children}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 opacity-60 transition-opacity hover:opacity-100"
        >
          <Icon name="close" className="text-[18px]" />
        </button>
      )}
    </div>
  )
}

/** Pill showing a document's ingestion state, matching the design's chips. */
export function StatusPill({ status }: { status: DocumentStatus }) {
  const isBusy = status === 'pending' || status === 'processing'

  const styles: Record<DocumentStatus, string> = {
    pending: 'bg-surface-container-highest text-on-surface-variant',
    processing: 'bg-surface-container-highest text-on-surface-variant',
    ready: 'bg-tertiary-container/30 text-on-tertiary-container',
    failed: 'bg-error-container/30 text-on-error-container',
  }
  const labels: Record<DocumentStatus, string> = {
    pending: 'Queued',
    processing: 'Indexing',
    ready: 'Ready',
    failed: 'Failed',
  }

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 font-mono text-[11px] font-medium uppercase tracking-wider whitespace-nowrap ${styles[status]}`}
    >
      {isBusy && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />}
      {labels[status]}
    </span>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-md py-xl text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/30 bg-primary/20 text-primary">
        <Icon name={icon} className="text-3xl" />
      </div>
      <h3 className="text-headline-md text-on-surface">{title}</h3>
      <p className="mt-2 max-w-sm text-body-md text-on-surface-variant">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Formatting helpers                                                         */
/* -------------------------------------------------------------------------- */

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Icon and accent color per file type, matching the design's card tiles. */
export function fileTypeVisual(fileType: string): { icon: string; tile: string } {
  switch (fileType) {
    case 'pdf':
      return { icon: 'picture_as_pdf', tile: 'bg-error-container/20 text-error' }
    case 'docx':
      return { icon: 'description', tile: 'bg-secondary-container/20 text-secondary' }
    default:
      return { icon: 'article', tile: 'bg-primary-container/20 text-primary' }
  }
}

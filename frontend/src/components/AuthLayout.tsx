import type { ReactNode } from 'react'
import { Icon } from './ui'

/**
 * Split-screen auth shell from the design: an atmospheric visual panel on the
 * left (desktop only) and the form on the right.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-dvh w-full">
      {/* Left: abstract visual */}
      <section className="relative hidden items-center justify-center overflow-hidden bg-surface-container-lowest lg:flex lg:w-1/2">
        <div className="absolute inset-0 z-0 bg-[radial-gradient(circle_at_center,var(--color-primary)_0%,transparent_60%)] opacity-10" />

        <div className="relative z-10 flex h-4/5 w-4/5 items-center justify-center">
          <div className="glass-panel relative flex h-full w-full flex-col justify-end overflow-hidden rounded-[2.5rem] p-12 shadow-2xl">
            {/* Node lattice, drawn rather than loaded, so nothing external is needed */}
            <svg
              className="absolute inset-0 h-full w-full opacity-40"
              viewBox="0 0 400 400"
              fill="none"
              aria-hidden="true"
            >
              <defs>
                <radialGradient id="node-glow">
                  <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0" />
                </radialGradient>
              </defs>
              {[
                [60, 80, 120, 150], [120, 150, 200, 110], [200, 110, 280, 170],
                [280, 170, 340, 120], [120, 150, 160, 250], [160, 250, 240, 290],
                [240, 290, 320, 240], [200, 110, 240, 290], [60, 80, 160, 250],
                [280, 170, 240, 290],
              ].map(([x1, y1, x2, y2], index) => (
                <line
                  key={index}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="var(--color-primary)"
                  strokeOpacity="0.35"
                  strokeWidth="1"
                />
              ))}
              {[
                [60, 80], [120, 150], [200, 110], [280, 170],
                [340, 120], [160, 250], [240, 290], [320, 240],
              ].map(([cx, cy], index) => (
                <g key={index}>
                  <circle cx={cx} cy={cy} r="18" fill="url(#node-glow)" />
                  <circle
                    cx={cx} cy={cy} r="3.5"
                    fill={index % 3 === 0 ? 'var(--color-tertiary)' : 'var(--color-primary)'}
                  />
                </g>
              ))}
            </svg>

            <div className="relative z-20">
              <h2 className="mb-2 text-headline-lg text-white">
                The Neural Layer for Enterprise Intelligence.
              </h2>
              <p className="max-w-md text-body-md text-on-surface-variant">
                CognitiveOS bridges the gap between raw data and actionable knowledge
                with retrieval-augmented AI reasoning.
              </p>
            </div>
          </div>

          {/* Floating "active reasoning" chip */}
          <div className="glass-panel shimmer-border absolute top-8 right-8 z-30 w-56 rounded-2xl p-4">
            <div className="mb-3 flex items-center gap-3">
              <div className="h-2 w-2 animate-pulse rounded-full bg-tertiary" />
              <span className="font-mono text-label-sm uppercase tracking-widest text-tertiary">
                Active Reasoning
              </span>
            </div>
            <div className="space-y-2">
              <div className="h-2 w-full rounded-full bg-white/10" />
              <div className="h-2 w-3/4 rounded-full bg-white/10" />
              <div className="h-2 w-5/6 rounded-full bg-white/10" />
            </div>
          </div>
        </div>
      </section>

      {/* Right: form */}
      <section className="relative flex w-full flex-col items-center justify-center bg-surface px-sm py-xl md:px-lg lg:w-1/2">
        <div className="absolute top-8 left-sm flex items-center gap-2 md:left-lg">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-container text-on-primary-container">
            <Icon name="auto_awesome" filled />
          </div>
          <span className="text-headline-md font-extrabold tracking-tight text-on-surface">
            CognitiveOS
          </span>
        </div>

        <div className="w-full max-w-[440px]">{children}</div>

        <div className="absolute right-8 bottom-8 hidden items-center gap-4 text-outline/20 sm:flex">
          <span className="font-mono text-label-sm tracking-tighter">
            COGNITIVE OS v1.0.0-STABLE
          </span>
        </div>
      </section>
    </main>
  )
}

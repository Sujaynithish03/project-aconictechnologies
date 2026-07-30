import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Icon, IconButton } from './ui'

const NAV_ITEMS = [
  { to: '/dashboard', icon: 'dashboard', label: 'Dashboard' },
  { to: '/chat', icon: 'forum', label: 'AI Chat' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-body-md transition-all ${
      isActive
        ? 'bg-primary-container/20 text-primary font-semibold'
        : 'text-on-surface-variant hover:bg-surface-container-high/50 hover:text-on-surface'
    }`

  return (
    <div className="min-h-dvh bg-background">
      {/* Backdrop for the mobile drawer */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — fixed on desktop, slide-in drawer on mobile */}
      <aside
        className={`fixed top-0 left-0 z-50 flex h-dvh w-64 flex-col border-r border-outline-variant/10 bg-surface-container-low py-md shadow-sm backdrop-blur-xl transition-transform duration-300 lg:translate-x-0 ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-3 px-sm pb-md">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-on-primary">
            <Icon name="memory" className="text-xl" filled />
          </div>
          <div className="min-w-0">
            <h1 className="text-headline-md font-bold leading-none text-primary-fixed-dim">
              CognitiveOS
            </h1>
            <p className="mt-1 font-mono text-label-sm text-on-surface-variant/60">
              AI Knowledge Base
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-xs" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={navClass}
              onClick={() => setIsSidebarOpen(false)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="px-xs">
          <button
            type="button"
            onClick={() => {
              setIsSidebarOpen(false)
              navigate('/dashboard')
            }}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container px-4 py-3 font-semibold text-on-primary-container shadow-lg transition-transform hover:scale-[1.02] active:scale-[0.98]"
          >
            <Icon name="add" />
            <span>New Document</span>
          </button>

          <div className="mt-md border-t border-outline-variant/10 pt-md">
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-body-md text-on-surface-variant transition-all hover:bg-surface-container-high/50 hover:text-on-surface"
            >
              <Icon name="logout" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-h-dvh flex-col lg:ml-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-outline-variant/10 bg-surface/60 px-sm backdrop-blur-3xl md:px-md">
          <div className="flex min-w-0 items-center gap-2">
            <IconButton
              icon="menu"
              label="Open navigation"
              className="lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
            />
            <span className="truncate font-mono text-label-sm uppercase tracking-widest text-outline">
              Enterprise Workspace
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="mx-2 hidden h-6 w-px bg-outline-variant/20 sm:block" />
            <div className="flex items-center gap-2 rounded-full border border-outline-variant/10 p-1 pl-3">
              <span className="hidden max-w-[12rem] truncate font-mono text-label-sm text-on-surface-variant sm:inline">
                {user?.email}
              </span>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container">
                <Icon name="person" className="text-[20px]" filled />
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

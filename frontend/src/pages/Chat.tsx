import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import * as chatApi from '../api/chat'
import * as documentsApi from '../api/documents'
import { toErrorMessage } from '../api/client'
import ChatMessage from '../components/ChatMessage'
import {
  Alert,
  Button,
  EmptyState,
  Icon,
  Spinner,
  fileTypeVisual,
} from '../components/ui'
import type { Document, Message } from '../types'

const SUGGESTIONS = [
  'Summarize this document.',
  'What are the key points?',
  'List all important dates.',
  'What is the refund policy?',
]

const ALL_DOCUMENTS = 'all'

export default function Chat() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const requestedDocument = searchParams.get('document')

  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedId, setSelectedId] = useState<string>(requestedDocument ?? ALL_DOCUMENTS)
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [isAsking, setIsAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const readyDocuments = useMemo(
    () => documents.filter((document) => document.status === 'ready'),
    [documents],
  )
  const documentFilter = selectedId === ALL_DOCUMENTS ? null : selectedId

  /* ---------------------------------------------------------------------- */
  /* Data loading                                                           */
  /* ---------------------------------------------------------------------- */

  useEffect(() => {
    let cancelled = false

    async function loadDocuments() {
      try {
        const { documents: fetched } = await documentsApi.listDocuments()
        if (cancelled) return
        setDocuments(fetched)

        // Drop a ?document= that no longer exists or isn't ready.
        const isUsable = fetched.some(
          (document) => document.id === requestedDocument && document.status === 'ready',
        )
        if (requestedDocument && !isUsable) {
          setSelectedId(ALL_DOCUMENTS)
          setSearchParams({}, { replace: true })
        }
      } catch (caught) {
        if (!cancelled) setError(toErrorMessage(caught, 'Could not load your documents.'))
      } finally {
        if (!cancelled) setIsLoadingDocuments(false)
      }
    }

    void loadDocuments()
    return () => {
      cancelled = true
    }
  }, [requestedDocument, setSearchParams])

  const loadHistory = useCallback(async (filter: string | null) => {
    setIsLoadingHistory(true)
    try {
      const { messages: fetched } = await chatApi.fetchHistory(filter)
      setMessages(fetched)
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not load chat history.'))
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    void loadHistory(documentFilter)
  }, [documentFilter, loadHistory])

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isAsking])

  /* ---------------------------------------------------------------------- */
  /* Asking                                                                 */
  /* ---------------------------------------------------------------------- */

  async function submitQuestion(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isAsking) return

    setError(null)
    setIsAsking(true)
    setQuestion('')

    // Optimistically render the question so the UI responds instantly.
    const optimistic: Message = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: trimmed,
      document_id: documentFilter,
      sources: null,
      created_at: new Date().toISOString(),
    }
    setMessages((previous) => [...previous, optimistic])

    try {
      const response = await chatApi.askQuestion(trimmed, documentFilter)
      setMessages((previous) => [
        ...previous,
        {
          id: response.message_id,
          role: 'assistant',
          content: response.answer,
          document_id: documentFilter,
          sources: response.sources,
          created_at: response.created_at,
        },
      ])
    } catch (caught) {
      // Roll the optimistic bubble back and restore the text for a retry.
      setMessages((previous) => previous.filter((message) => message.id !== optimistic.id))
      setQuestion(trimmed)
      setError(toErrorMessage(caught, 'Could not get an answer.'))
    } finally {
      setIsAsking(false)
      inputRef.current?.focus()
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void submitQuestion(question)
  }

  function selectDocument(value: string) {
    setSelectedId(value)
    setSearchParams(value === ALL_DOCUMENTS ? {} : { document: value }, { replace: true })
  }

  /* ---------------------------------------------------------------------- */
  /* Render                                                                 */
  /* ---------------------------------------------------------------------- */

  if (isLoadingDocuments) {
    return (
      <div className="flex items-center justify-center gap-3 py-xl text-body-md text-on-surface-variant">
        <Spinner className="h-5 w-5" />
        Loading workspace…
      </div>
    )
  }

  if (readyDocuments.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-sm py-lg md:px-lg">
        <div className="glass-card rounded-2xl">
          <EmptyState
            icon="forum"
            title="No indexed documents yet"
            description="Upload a document and wait for indexing to finish, then come back to query it with AI."
            action={<Button onClick={() => navigate('/dashboard')}>Go to Knowledge Base</Button>}
          />
        </div>
      </div>
    )
  }

  const scopeLabel =
    readyDocuments.find((document) => document.id === selectedId)?.filename ??
    'all documents'

  return (
    <div className="flex h-[calc(100dvh-4rem)]">
      {/* Source selector — the design's secondary sidebar */}
      <aside className="custom-scrollbar hidden w-72 shrink-0 flex-col overflow-y-auto border-r border-outline-variant/10 bg-surface-container-low/30 p-sm lg:flex">
        <h3 className="mb-4 font-mono text-label-sm uppercase tracking-widest text-outline">
          Context Sources
        </h3>

        <button
          type="button"
          onClick={() => selectDocument(ALL_DOCUMENTS)}
          className={`mb-2 flex w-full items-center gap-3 rounded-lg p-2.5 text-left text-body-md transition-all ${
            selectedId === ALL_DOCUMENTS
              ? 'bg-primary-container/20 text-primary font-semibold'
              : 'text-on-surface-variant hover:bg-surface-container-high/50'
          }`}
        >
          <Icon name="all_inclusive" className="text-[20px]" />
          <span className="flex-1 truncate">All documents</span>
          <span className="font-mono text-[11px] text-outline">
            {readyDocuments.length}
          </span>
        </button>

        <div className="space-y-1">
          {readyDocuments.map((document) => {
            const visual = fileTypeVisual(document.file_type)
            const isSelected = document.id === selectedId
            return (
              <button
                key={document.id}
                type="button"
                onClick={() => selectDocument(document.id)}
                title={document.filename}
                className={`flex w-full items-center gap-3 rounded-lg p-2.5 text-left transition-all ${
                  isSelected
                    ? 'bg-primary-container/20 text-primary'
                    : 'text-on-surface-variant hover:bg-surface-container-high/50'
                }`}
              >
                <Icon name={visual.icon} className="shrink-0 text-[20px]" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-label-sm font-medium">
                    {document.filename}
                  </span>
                  <span className="block font-mono text-[11px] text-outline">
                    {document.chunk_count} chunks
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        <div className="mt-auto pt-md">
          <Button variant="outline" className="w-full" onClick={() => navigate('/dashboard')}>
            <Icon name="add" className="text-[20px]" />
            Add document
          </Button>
        </div>
      </aside>

      {/* Conversation */}
      <section className="flex min-w-0 flex-1 flex-col">
        {/* Mobile scope picker */}
        <div className="border-b border-outline-variant/10 p-sm lg:hidden">
          <label
            htmlFor="document-select"
            className="mb-1.5 block font-mono text-label-sm uppercase tracking-widest text-outline"
          >
            Context Source
          </label>
          <select
            id="document-select"
            value={selectedId}
            onChange={(event) => selectDocument(event.target.value)}
            className="w-full rounded-xl border border-outline-variant/30 bg-surface-container px-3 py-2.5 text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/50"
          >
            <option value={ALL_DOCUMENTS}>All documents ({readyDocuments.length})</option>
            {readyDocuments.map((document) => (
              <option key={document.id} value={document.id}>
                {document.filename}
              </option>
            ))}
          </select>
        </div>

        <div className="custom-scrollbar flex-1 space-y-6 overflow-y-auto p-sm md:p-md">
          {isLoadingHistory ? (
            <div className="flex items-center justify-center gap-3 py-lg text-body-md text-on-surface-variant">
              <Spinner className="h-5 w-5" />
              Loading history…
            </div>
          ) : messages.length === 0 ? (
            <div className="py-lg text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/30 bg-primary/20 text-primary">
                <Icon name="auto_awesome" className="animate-pulse text-3xl" filled />
              </div>
              <h2 className="text-headline-md text-on-surface">
                Query your knowledge base
              </h2>
              <p className="mx-auto mt-2 max-w-md text-body-md text-on-surface-variant">
                Answers are grounded in{' '}
                <span className="text-primary">{scopeLabel}</span> and cite the exact
                passages they came from.
              </p>
              <div className="mx-auto mt-6 flex max-w-lg flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void submitQuestion(suggestion)}
                    className="rounded-full border border-outline-variant/30 bg-surface-container/60 px-4 py-2 text-label-sm text-on-surface-variant transition-all hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => <ChatMessage key={message.id} message={message} />)
          )}

          {isAsking && (
            <div className="flex justify-start gap-3" aria-live="polite">
              <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary">
                <Icon name="auto_awesome" className="text-[18px]" filled />
              </div>
              <div className="glass-card flex items-center gap-3 rounded-2xl rounded-bl-md px-4 py-3.5">
                <span className="sr-only">Reasoning…</span>
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="h-2 w-2 animate-bounce rounded-full bg-primary"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
                <span className="font-mono text-label-sm uppercase tracking-widest text-outline">
                  Reasoning
                </span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="px-sm pb-2 md:px-md">
            <Alert onDismiss={() => setError(null)}>{error}</Alert>
          </div>
        )}

        {/* Composer */}
        <form onSubmit={handleSubmit} className="border-t border-outline-variant/10 p-sm md:p-md">
          <div className="glass-panel flex items-center gap-2 rounded-full py-2 pr-2 pl-4">
            <Icon name="search" className="shrink-0 text-[20px] text-outline" />
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask anything about your documents…"
              maxLength={2000}
              disabled={isAsking}
              aria-label="Your question"
              className="min-w-0 flex-1 border-none bg-transparent text-body-md text-on-surface outline-none placeholder:text-outline-variant disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={isAsking || !question.trim()}
              aria-label="Send question"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg transition-transform hover:scale-105 active:scale-95 disabled:pointer-events-none disabled:opacity-40"
            >
              {isAsking ? <Spinner className="h-5 w-5" /> : <Icon name="send" />}
            </button>
          </div>
          <p className="mt-2 text-center font-mono text-[11px] text-outline/50">
            Grounded in {scopeLabel} · answers include source citations
          </p>
        </form>
      </section>
    </div>
  )
}

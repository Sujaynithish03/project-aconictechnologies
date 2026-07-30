import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toErrorMessage } from '../api/client'
import * as documentsApi from '../api/documents'
import FileDropzone from '../components/FileDropzone'
import {
  Alert,
  Button,
  EmptyState,
  Icon,
  Spinner,
  StatusPill,
  fileTypeVisual,
  formatBytes,
  formatDateTime,
} from '../components/ui'
import type { Document } from '../types'

const POLL_INTERVAL_MS = 2000

export default function Dashboard() {
  const navigate = useNavigate()

  const [documents, setDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const pollRef = useRef<number | null>(null)

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsLoading(true)
    try {
      const { documents: fetched } = await documentsApi.listDocuments()
      setDocuments(fetched)
      setError(null)
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not load your documents.'))
    } finally {
      if (showSpinner) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(true)
  }, [load])

  // Poll only while something is still being processed, then stop.
  const hasPendingWork = documents.some(
    (document) => document.status === 'pending' || document.status === 'processing',
  )

  useEffect(() => {
    if (!hasPendingWork) {
      if (pollRef.current) {
        window.clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }

    pollRef.current = window.setInterval(() => void load(), POLL_INTERVAL_MS)
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [hasPendingWork, load])

  async function handleUpload(file: File) {
    setIsUploading(true)
    setUploadProgress(0)
    setError(null)
    setNotice(null)
    try {
      // Phase 1: upload + text extraction. Returns quickly as `pending`.
      const created = await documentsApi.uploadDocument(file, setUploadProgress)
      setDocuments((previous) => [created, ...previous])
      setNotice(`"${created.filename}" uploaded. Indexing now…`)

      // Phase 2: embedding. Deliberately not awaited — the status pill and
      // polling communicate progress, so the UI stays responsive either way.
      void documentsApi
        .processDocument(created.id)
        .then((processed) =>
          setDocuments((previous) =>
            previous.map((item) => (item.id === processed.id ? processed : item)),
          ),
        )
        .catch(() => {
          // Polling will surface whatever state the server recorded.
          void load()
        })
    } catch (caught) {
      setError(toErrorMessage(caught, 'Upload failed.'))
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  async function handleRetry(document: Document) {
    setError(null)
    setDocuments((previous) =>
      previous.map((item) =>
        item.id === document.id
          ? { ...item, status: 'processing', error_message: null }
          : item,
      ),
    )
    try {
      const processed = await documentsApi.processDocument(document.id)
      setDocuments((previous) =>
        previous.map((item) => (item.id === processed.id ? processed : item)),
      )
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not reprocess the document.'))
      void load()
    }
  }

  async function handleDelete(document: Document) {
    if (!window.confirm(`Delete "${document.filename}"? This cannot be undone.`)) return

    setDeletingId(document.id)
    setError(null)
    try {
      await documentsApi.deleteDocument(document.id)
      setDocuments((previous) => previous.filter((item) => item.id !== document.id))
      setNotice(`"${document.filename}" deleted.`)
    } catch (caught) {
      setError(toErrorMessage(caught, 'Could not delete the document.'))
    } finally {
      setDeletingId(null)
    }
  }

  const readyCount = documents.filter((document) => document.status === 'ready').length
  const totalChunks = documents.reduce((sum, document) => sum + document.chunk_count, 0)

  return (
    <div className="mx-auto max-w-6xl px-sm py-lg md:px-lg">
      {/* Page header */}
      <div className="mb-lg flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="mb-2 text-headline-lg text-on-surface">Knowledge Base</h2>
          <p className="max-w-lg text-body-md text-on-surface-variant">
            Upload documents to build your corpus, then query them with grounded AI
            reasoning.
          </p>
        </div>
        {readyCount > 0 && (
          <Button onClick={() => navigate('/chat')}>
            <Icon name="forum" className="text-[20px]" />
            Ask a question
          </Button>
        )}
      </div>

      {/* Stat strip */}
      {documents.length > 0 && (
        <div className="mb-md grid grid-cols-2 gap-4 sm:grid-cols-3">
          {[
            { label: 'Documents', value: documents.length, icon: 'folder' },
            { label: 'Indexed', value: readyCount, icon: 'check_circle' },
            { label: 'Vector Chunks', value: totalChunks, icon: 'scatter_plot' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="glass-card flex items-center gap-4 rounded-2xl p-4"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container/20 text-primary">
                <Icon name={stat.icon} className="text-[22px]" />
              </div>
              <div className="min-w-0">
                <p className="text-headline-md text-on-surface">{stat.value}</p>
                <p className="truncate font-mono text-label-sm uppercase tracking-wider text-on-surface-variant/60">
                  {stat.label}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mb-md">
        <FileDropzone
          onFileSelected={handleUpload}
          isUploading={isUploading}
          uploadProgress={uploadProgress}
        />
      </div>

      <div className="mb-md space-y-3">
        {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
        {notice && (
          <Alert tone="success" onDismiss={() => setNotice(null)}>
            {notice}
          </Alert>
        )}
      </div>

      {/* Document grid */}
      {isLoading ? (
        <div className="flex items-center justify-center gap-3 py-xl text-body-md text-on-surface-variant">
          <Spinner className="h-5 w-5" />
          Loading documents…
        </div>
      ) : documents.length === 0 ? (
        <div className="glass-card rounded-2xl">
          <EmptyState
            icon="folder_open"
            title="No documents yet"
            description="Upload a PDF, DOCX, or TXT file above to start building your knowledge base."
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {documents.map((document) => {
            const visual = fileTypeVisual(document.file_type)
            const isBusy =
              document.status === 'pending' || document.status === 'processing'

            return (
              <article
                key={document.id}
                className={`glass-card flex flex-col justify-between rounded-2xl p-6 ${
                  isBusy ? 'shimmer-border' : ''
                }`}
              >
                <div>
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div
                      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${visual.tile}`}
                    >
                      <Icon name={visual.icon} className="text-3xl" />
                    </div>
                    <StatusPill status={document.status} />
                  </div>

                  <h3
                    className="mb-1 truncate text-lg font-semibold text-on-surface"
                    title={document.filename}
                  >
                    {document.filename}
                  </h3>
                  <p className="font-mono text-label-sm text-on-surface-variant">
                    {formatBytes(document.size_bytes)}
                    {document.chunk_count > 0 && ` · ${document.chunk_count} chunks`}
                    {document.char_count > 0 &&
                      ` · ${document.char_count.toLocaleString()} chars`}
                  </p>

                  {document.status === 'failed' && document.error_message && (
                    <p className="mt-3 rounded-lg bg-error-container/20 px-3 py-2 text-label-sm text-on-error-container">
                      {document.error_message}
                    </p>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-outline-variant/10 pt-4">
                  <span className="font-mono text-[12px] text-on-surface-variant/60">
                    {formatDateTime(document.created_at)}
                  </span>
                  <div className="flex items-center gap-1">
                    {document.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => handleRetry(document)}
                        aria-label={`Retry indexing ${document.filename}`}
                        title="Retry indexing"
                        className="rounded-full p-2 text-primary transition-colors hover:bg-primary/10"
                      >
                        <Icon name="refresh" className="text-[20px]" />
                      </button>
                    )}
                    {document.status === 'ready' && (
                      <Link
                        to={`/chat?document=${document.id}`}
                        aria-label={`Ask about ${document.filename}`}
                        title="Ask about this document"
                        className="rounded-full p-2 text-primary transition-colors hover:bg-primary/10"
                      >
                        <Icon name="forum" className="text-[20px]" />
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(document)}
                      disabled={deletingId === document.id}
                      aria-label={`Delete ${document.filename}`}
                      title="Delete"
                      className="rounded-full p-2 text-on-surface-variant transition-colors hover:bg-error/10 hover:text-error disabled:opacity-40"
                    >
                      {deletingId === document.id ? (
                        <Spinner className="h-5 w-5" />
                      ) : (
                        <Icon name="delete" className="text-[20px]" />
                      )}
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

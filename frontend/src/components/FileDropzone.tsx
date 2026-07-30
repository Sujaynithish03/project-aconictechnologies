import { useRef, useState, type DragEvent } from 'react'
import { Icon, Spinner } from './ui'

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt']
const MAX_MB = 10

interface FileDropzoneProps {
  onFileSelected: (file: File) => void
  isUploading: boolean
  uploadProgress: number
  disabled?: boolean
}

/**
 * Drag-and-drop upload target. Validates type and size client-side so obvious
 * mistakes never cost a round trip; the server re-validates regardless.
 */
export default function FileDropzone({
  onFileSelected,
  isUploading,
  uploadProgress,
  disabled = false,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const isBusy = isUploading || disabled

  function validate(file: File): string | null {
    const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      return `"${file.name}" is not supported. Choose a PDF, DOCX, or TXT file.`
    }
    if (file.size === 0) return 'That file is empty.'
    if (file.size > MAX_MB * 1024 * 1024) {
      return `That file is ${(file.size / 1_048_576).toFixed(1)} MB. The limit is ${MAX_MB} MB.`
    }
    return null
  }

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (!file) return

    const error = validate(file)
    setLocalError(error)
    if (!error) onFileSelected(file)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    if (!isBusy) handleFiles(event.dataTransfer.files)
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          if (!isBusy) setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`group relative flex h-48 w-full flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed transition-all ${
          isDragging
            ? 'border-primary bg-primary/10'
            : 'border-primary/40 bg-primary/5 hover:border-primary/70'
        } ${isBusy ? 'opacity-80' : ''}`}
      >
        {isUploading ? (
          <>
            <Spinner className="h-8 w-8 text-primary" />
            <p className="text-body-lg text-on-surface">Uploading… {uploadProgress}%</p>
            <div
              className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-surface-container-highest"
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full bg-primary transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </>
        ) : (
          <>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/20 text-primary transition-transform group-hover:scale-110">
              <Icon name="cloud_upload" className="text-3xl" />
            </div>
            <p className="text-body-lg text-on-surface">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                disabled={isBusy}
                className="font-semibold text-primary hover:underline disabled:pointer-events-none"
              >
                Choose a file
              </button>{' '}
              or drag it here
            </p>
            <p className="mt-1 font-mono text-label-sm text-on-surface-variant">
              PDF, DOCX or TXT · up to {MAX_MB} MB
            </p>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(event) => {
            handleFiles(event.target.files)
            // Reset so selecting the same file twice still fires onChange.
            event.target.value = ''
          }}
        />
      </div>

      {localError && (
        <p role="alert" className="mt-2 text-body-md text-error">
          {localError}
        </p>
      )}
    </div>
  )
}

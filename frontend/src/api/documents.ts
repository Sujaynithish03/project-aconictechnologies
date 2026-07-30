import { api } from './client'
import type { Document, DocumentListResponse } from '../types'

export async function uploadDocument(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Document> {
  const form = new FormData()
  form.append('file', file)

  const { data } = await api.post<Document>('/upload', form, {
    // Let the browser set the multipart boundary.
    headers: { 'Content-Type': undefined },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

/**
 * Kick off chunking and embedding for an uploaded document.
 * Safe to call again on a failed document — it retries without a re-upload.
 */
export async function processDocument(id: string): Promise<Document> {
  const { data } = await api.post<Document>(`/documents/${id}/process`)
  return data
}

export async function listDocuments(): Promise<DocumentListResponse> {
  const { data } = await api.get<DocumentListResponse>('/documents')
  return data
}

export async function getDocument(id: string): Promise<Document> {
  const { data } = await api.get<Document>(`/documents/${id}`)
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`)
}

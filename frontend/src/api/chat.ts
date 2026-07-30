import { api } from './client'
import type { AskResponse, HistoryResponse } from '../types'

export async function askQuestion(
  question: string,
  documentId?: string | null,
): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>('/ask', {
    question,
    // Omitting document_id tells the backend to search every ready document.
    document_id: documentId ?? null,
  })
  return data
}

export async function fetchHistory(documentId?: string | null): Promise<HistoryResponse> {
  const { data } = await api.get<HistoryResponse>('/history', {
    params: documentId ? { document_id: documentId } : undefined,
  })
  return data
}

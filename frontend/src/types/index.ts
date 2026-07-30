/** Shapes mirroring the backend's Pydantic schemas. */

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface User {
  id: string
  email: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Document {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  status: DocumentStatus
  error_message: string | null
  char_count: number
  chunk_count: number
  created_at: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}

export interface SourceChunk {
  document_id: string
  document_name: string
  chunk_index: number
  snippet: string
  similarity: number
}

export interface AskResponse {
  message_id: string
  question: string
  answer: string
  sources: SourceChunk[]
  created_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  document_id: string | null
  sources: SourceChunk[] | null
  created_at: string
}

export interface HistoryResponse {
  messages: Message[]
  total: number
}

import { useState } from 'react'
import type { Message, SourceChunk } from '../types'
import { Icon, formatDateTime } from './ui'

/**
 * Renders the small subset of markdown the model is asked to produce
 * (bullets, numbered lists, bold, inline code) as escaped HTML.
 * A full markdown library would be overkill for this surface.
 */
function renderAnswer(text: string): string {
  const escape = (value: string) =>
    value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  const inline = (value: string) =>
    escape(value)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      // Citation markers like [1] get a subtle accent.
      .replace(
        /\[(\d+)\]/g,
        '<span class="text-primary font-semibold font-mono text-[0.85em]">[$1]</span>',
      )

  const blocks: string[] = []
  let listItems: string[] = []
  let listType: 'ul' | 'ol' | null = null

  const flushList = () => {
    if (listType && listItems.length) {
      blocks.push(`<${listType}>${listItems.join('')}</${listType}>`)
    }
    listItems = []
    listType = null
  }

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) {
      flushList()
      continue
    }

    const bullet = line.match(/^[-*•]\s+(.*)$/)
    const numbered = line.match(/^\d+[.)]\s+(.*)$/)

    if (bullet) {
      if (listType !== 'ul') flushList()
      listType = 'ul'
      listItems.push(`<li>${inline(bullet[1])}</li>`)
    } else if (numbered) {
      if (listType !== 'ol') flushList()
      listType = 'ol'
      listItems.push(`<li>${inline(numbered[1])}</li>`)
    } else {
      flushList()
      blocks.push(`<p>${inline(line)}</p>`)
    }
  }
  flushList()

  return blocks.join('')
}

function SourceList({ sources }: { sources: SourceChunk[] }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="mt-4 border-t border-outline-variant/10 pt-3">
      <button
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-expanded={isOpen}
        className="inline-flex items-center gap-1.5 rounded bg-primary/20 px-2 py-0.5 font-mono text-[12px] font-bold text-primary transition-colors hover:bg-primary/30"
      >
        <Icon name="hub" className="text-[14px]" />
        {sources.length} source{sources.length === 1 ? '' : 's'}
        <Icon name={isOpen ? 'expand_less' : 'expand_more'} className="text-[16px]" />
      </button>

      {isOpen && (
        <ol className="mt-3 space-y-2">
          {sources.map((source, index) => (
            <li
              key={`${source.document_id}-${source.chunk_index}`}
              className="rounded-xl border border-outline-variant/10 bg-surface-container-low/60 p-3"
            >
              <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] uppercase tracking-wider">
                <span className="font-bold text-primary">[{index + 1}]</span>
                <span className="truncate text-on-surface-variant">
                  {source.document_name}
                </span>
                <span className="text-outline">
                  chunk {source.chunk_index} ·{' '}
                  <span className="text-tertiary">
                    {(source.similarity * 100).toFixed(0)}% match
                  </span>
                </span>
              </div>
              <p className="text-label-sm leading-relaxed whitespace-pre-wrap text-on-surface-variant/70">
                {source.snippet}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function ChatMessage({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary-container px-4 py-3 text-body-md text-on-primary-container shadow-lg sm:max-w-[70%]">
          <p className="whitespace-pre-wrap">{message.content}</p>
          <p className="mt-1 text-right font-mono text-[11px] text-on-primary-container/60">
            {formatDateTime(message.created_at)}
          </p>
        </div>
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container">
          <Icon name="person" className="text-[18px]" filled />
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary">
        <Icon name="auto_awesome" className="text-[18px]" filled />
      </div>
      <div className="glass-card max-w-[90%] rounded-2xl rounded-bl-md px-4 py-3 sm:max-w-[78%]">
        <div
          className="answer-body text-body-md leading-relaxed text-on-surface"
          // Model-generated text; renderAnswer escapes it before re-introducing
          // only the tags it produced itself.
          dangerouslySetInnerHTML={{ __html: renderAnswer(message.content) }}
        />
        {message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}
        <p className="mt-2 font-mono text-[11px] text-on-surface-variant/50">
          {formatDateTime(message.created_at)}
        </p>
      </div>
    </div>
  )
}

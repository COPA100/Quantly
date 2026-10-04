export interface SseMessage {
  event: string
  data: string
}

// minimal server-sent events parser: yields one message per blank-line
// terminated block. comment lines (": ping") are skipped.
export async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let event = 'message'
  let data: string[] = []

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) return
      buffer += decoder.decode(value, { stream: true })

      let newline: number
      while ((newline = buffer.search(/\r\n|\n|\r/)) !== -1) {
        // a trailing cr may be half of a crlf split across chunks, wait for more
        if (buffer[newline] === '\r' && newline === buffer.length - 1) break
        const line = buffer.slice(0, newline)
        buffer = buffer.slice(newline + (buffer.startsWith('\r\n', newline) ? 2 : 1))

        if (line === '') {
          if (data.length > 0) yield { event, data: data.join('\n') }
          event = 'message'
          data = []
        } else if (!line.startsWith(':')) {
          const colon = line.indexOf(':')
          const field = colon === -1 ? line : line.slice(0, colon)
          let content = colon === -1 ? '' : line.slice(colon + 1)
          if (content.startsWith(' ')) content = content.slice(1)
          if (field === 'event') event = content
          else if (field === 'data') data.push(content)
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined)
  }
}

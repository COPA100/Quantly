import { describe, expect, it } from 'vitest'
import { parseSse, type SseMessage } from './sse'

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

async function collect(body: ReadableStream<Uint8Array>): Promise<SseMessage[]> {
  const out: SseMessage[] = []
  for await (const message of parseSse(body)) out.push(message)
  return out
}

describe('parseSse', () => {
  it('parses a named event', async () => {
    const messages = await collect(streamOf('event: status\ndata: {"id":1}\n\n'))
    expect(messages).toEqual([{ event: 'status', data: '{"id":1}' }])
  })

  it('defaults the event name to message', async () => {
    expect(await collect(streamOf('data: hi\n\n'))).toEqual([{ event: 'message', data: 'hi' }])
  })

  it('skips heartbeat comments', async () => {
    const messages = await collect(streamOf(': ping\n\n', 'data: a\n\n', ': ping\n\n'))
    expect(messages).toEqual([{ event: 'message', data: 'a' }])
  })

  it('joins multi-line data', async () => {
    expect(await collect(streamOf('data: one\ndata: two\n\n'))).toEqual([
      { event: 'message', data: 'one\ntwo' },
    ])
  })

  it('handles messages split across chunks, including a split crlf', async () => {
    const messages = await collect(streamOf('event: sta', 'tus\r', '\ndata: x\r\n', '\r\n'))
    expect(messages).toEqual([{ event: 'status', data: 'x' }])
  })

  it('drops an unterminated trailing block', async () => {
    expect(await collect(streamOf('data: a\n\ndata: partial'))).toEqual([
      { event: 'message', data: 'a' },
    ])
  })
})

import { type DragEvent, type KeyboardEvent, useRef, useState } from 'react'

interface Props {
  onFile: (file: File) => void
  accept?: string
}

export default function Dropzone({ onFile, accept = '.csv' }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) onFile(file)
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      onKeyDown={handleKeyDown}
      className={`flex min-h-[320px] cursor-pointer flex-col items-center justify-center rounded-[var(--radius-panel)] border border-dashed px-6 text-center transition-colors ${
        dragging ? 'border-ink bg-surface' : 'border-hairline-strong bg-canvas-soft hover:border-ink'
      }`}
    >
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="text-muted">
        <path
          d="M12 15V4m0 0-4 4m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <p className="mt-4 text-[17px] text-ink">Drop your positions CSV here</p>
      <p className="mt-1 text-sm text-muted">or click to choose a file</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onFile(file)
        }}
      />
    </div>
  )
}

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
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
        dragging
          ? 'border-indigo-400 bg-indigo-50'
          : 'border-slate-300 bg-white hover:border-slate-400'
      }`}
    >
      <p className="text-sm font-medium text-slate-700">Drop your holdings CSV here</p>
      <p className="mt-1 text-xs text-slate-500">or click to browse</p>
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

import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Dropzone from '../components/Dropzone'
import { errorMessage } from '../lib/api'
import { uploadPortfolio } from '../lib/portfolio-api'

const SAMPLE = `"Symbol","Qty (Quantity)","Cost Basis"
"AAPL","120","$19,500.00"
"VOO","150","$82,500.00"`

export default function UploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)

  const mutation = useMutation({
    mutationFn: (selected: File) => uploadPortfolio(selected),
    onSuccess: (accepted) => navigate(`/portfolios/${accepted.id}`),
  })

  return (
    <div className="grid gap-12 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <h1 className="display-xl text-ink">Upload a portfolio</h1>
        <p className="mt-3 max-w-[52ch] text-body">
          Export your positions from your brokerage as a CSV. Quantly reads the symbol, quantity and
          cost basis columns, and ignores cash and total rows.
        </p>
        <h2 className="mt-10 text-[15px] font-medium text-ink">The columns it needs</h2>
        <pre className="num mt-3 overflow-x-auto rounded-[var(--radius-panel)] border border-hairline bg-surface p-4 text-[12.5px] leading-relaxed text-body">
          {SAMPLE}
        </pre>
        <p className="mt-3 text-sm text-muted">
          Other columns are ignored, and the file name becomes the portfolio name.
        </p>
      </div>

      <div className="lg:col-span-7">
        <Dropzone onFile={setFile} />

        {file && (
          <div className="mt-4 flex items-center justify-between gap-4 rounded-[var(--radius-panel)] border border-hairline bg-surface px-5 py-4">
            <span className="num truncate text-sm text-ink">{file.name}</span>
            <Button onClick={() => mutation.mutate(file)} disabled={mutation.isPending}>
              {mutation.isPending ? 'Uploading' : 'Analyze'}
            </Button>
          </div>
        )}

        {mutation.isError && <p className="mt-3 text-sm text-loss">{errorMessage(mutation.error)}</p>}
      </div>
    </div>
  )
}

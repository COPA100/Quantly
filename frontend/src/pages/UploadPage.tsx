import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Dropzone from '../components/Dropzone'
import { errorMessage } from '../lib/api'
import { uploadPortfolio } from '../lib/portfolio-api'

export default function UploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)

  const mutation = useMutation({
    mutationFn: (selected: File) => uploadPortfolio(selected),
    onSuccess: (accepted) => navigate(`/portfolios/${accepted.id}`),
  })

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold text-slate-900">Upload a portfolio</h1>
      <p className="mt-1 text-sm text-slate-500">
        Export your holdings as CSV from your brokerage and drop it below.
      </p>

      <div className="mt-6">
        <Dropzone onFile={setFile} />

        {file && (
          <div className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-4 py-3">
            <span className="truncate text-sm text-slate-700">{file.name}</span>
            <Button onClick={() => mutation.mutate(file)} disabled={mutation.isPending}>
              {mutation.isPending ? 'Uploading…' : 'Analyze'}
            </Button>
          </div>
        )}

        {mutation.isError && (
          <p className="mt-3 text-sm text-red-600">{errorMessage(mutation.error)}</p>
        )}
      </div>
    </div>
  )
}

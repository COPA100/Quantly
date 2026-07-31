import Spinner from './Spinner'

export default function AnalysisProgress({ status }: { status: string }) {
  if (status === 'failed') {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Analysis failed. Try uploading the file again.
      </div>
    )
  }

  const label = status === 'pending' ? 'Queued for analysis…' : 'Analyzing your portfolio…'
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
      <Spinner />
      <span className="text-sm text-slate-600">{label}</span>
    </div>
  )
}

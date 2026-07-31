const styles: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-600',
  processing: 'bg-amber-100 text-amber-700',
  complete: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
}

export default function StatusBadge({ status }: { status: string }) {
  const cls = styles[status] ?? 'bg-slate-100 text-slate-600'
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {status}
    </span>
  )
}

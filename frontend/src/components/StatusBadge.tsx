import { pillClass, STAGE_STYLE } from '../lib/ui'

export default function StatusBadge({ status }: { status: string }) {
  const stage = STAGE_STYLE[status] ?? { label: status, className: 'bg-surface-strong text-ink' }
  return <span className={`${pillClass} ${stage.className}`}>{stage.label}</span>
}

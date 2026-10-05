// shared class strings for controls, kept out of component files

const buttonBase =
  'inline-flex h-10 items-center justify-center gap-2 rounded-[var(--radius-control)] px-[18px] text-sm font-medium leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-50'

// primary is the only orange in the app. secondary is white on cream.
export const buttonVariants = {
  primary: `${buttonBase} bg-primary text-white hover:bg-primary-active active:bg-primary-active`,
  secondary: `${buttonBase} border border-hairline-strong bg-surface text-ink hover:border-ink`,
  ink: `${buttonBase} bg-ink text-canvas hover:bg-black`,
}

export const pillClass =
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase leading-none tracking-[0.08em]'

// the analysis pipeline vocabulary, shared by the list and the detail header.
// these pastels are reserved for job stages and appear nowhere else.
export const STAGE_STYLE: Record<string, { label: string; className: string }> = {
  pending: { label: 'Queued', className: 'bg-stage-queue text-ink' },
  processing: { label: 'Analyzing', className: 'bg-stage-analyze text-ink' },
  complete: { label: 'Done', className: 'bg-stage-done text-white' },
  failed: { label: 'Failed', className: 'bg-loss text-white' },
}

import type { InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export default function TextField({ label, id, className = '', ...props }: Props) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={id}
        className={`mt-1.5 block h-11 w-full rounded-[var(--radius-control)] border border-hairline-strong bg-surface px-4 text-[15px] text-ink placeholder:text-muted-soft focus:border-ink focus:outline-none ${className}`}
        {...props}
      />
    </div>
  )
}

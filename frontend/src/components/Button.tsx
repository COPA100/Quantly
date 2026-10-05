import type { ButtonHTMLAttributes } from 'react'
import { buttonVariants } from '../lib/ui'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof buttonVariants
}

export default function Button({ variant = 'primary', className = '', ...props }: Props) {
  return <button className={`${buttonVariants[variant]} ${className}`} {...props} />
}

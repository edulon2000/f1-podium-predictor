// Based on "Focus Field" from the microkit registry (by henriquegpb):
//   npx shadcn@latest add @microkit/focus-input — https://microkit.co/components/focus-input
// Adapted for this project: controlled value, label/placeholder props, and the project's
// tokens (night border on focus + sun halo) instead of the hard-coded orange. The animated
// focus treatment and its timing (320 ms, cubic-bezier(.22,1,.36,1)) are kept as-is and are
// also the project's global motion token.

import type { ChangeEvent } from 'react'
import { track } from '@/analytics'

interface FocusFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  id?: string
  className?: string
}

export function FocusField({ label, value, onChange, placeholder, id, className = '' }: FocusFieldProps) {
  const inputId = id ?? `focus-${label.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <label htmlFor={inputId} className={`block w-full max-w-[260px] ${className}`}>
      <span className="label mb-[7px] block">{label}</span>
      <input
        id={inputId}
        type="search"
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
        onBlur={(e) => e.target.value && track('search', { field: label, query: e.target.value.slice(0, 40) })}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full rounded-[5px] border border-rule bg-paper px-2.5 py-2 text-[13px] text-night placeholder:text-dash shadow-[0_0_0_0_#f3d27a00] outline-none transition-[border-color,box-shadow] duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] focus:border-night focus:shadow-[0_0_0_3px_#f3d27a] motion-reduce:transition-none"
      />
    </label>
  )
}

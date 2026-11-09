import { MorphIcon, type MorphIconProps } from 'morphicons/react'

/** The one morphing-icon style used everywhere: same spring, stroke and reduced-motion policy. */
const SPRING = 'snappy' as const

export function Morph(props: MorphIconProps) {
  return <MorphIcon size={18} strokeWidth={1.75} spring={SPRING} reducedMotion="user" {...props} />
}

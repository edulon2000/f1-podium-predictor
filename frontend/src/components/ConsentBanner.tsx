import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { clarityConfigured, getConsent, setConsent } from '@/analytics'

/**
 * Consent for the optional cookie-based tool (Clarity). Accept and Decline are equally easy,
 * as GDPR/LGPD require; nothing cookie-based loads before "Accept".
 */
export function ConsentBanner() {
  const [open, setOpen] = useState(() => clarityConfigured() && getConsent() === null)

  useEffect(() => {
    const reopen = () => setOpen(clarityConfigured())
    window.addEventListener('analytics-consent-reset', reopen)
    return () => window.removeEventListener('analytics-consent-reset', reopen)
  }, [])

  if (!open) return null
  const choose = (c: 'granted' | 'denied') => {
    setConsent(c)
    setOpen(false)
  }
  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie choice"
      className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-2xl rounded-xl border border-night bg-stone/95 p-4 shadow-[0_18px_40px_-20px_rgba(12,16,24,0.5)] backdrop-blur sm:inset-x-6 sm:p-5"
    >
      <p className="wide text-sm font-extrabold uppercase">Help me improve this site?</p>
      <p className="mt-1.5 text-[13px] leading-snug text-earth">
        I count visits anonymously, without cookies. If you accept, I also use Microsoft Clarity, which sets cookies to
        record how pages are used (clicks and scrolling, never what you type) so I can see what is confusing. You can
        change this anytime in “Cookie settings” at the bottom of the page.{' '}
        <Link to="/privacy" className="underline underline-offset-2 hover:text-night">
          Privacy details
        </Link>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() => choose('granted')}
          className="rounded-full bg-night px-4 py-2 font-mono text-[0.72rem] tracking-[0.08em] text-stone uppercase transition-colors duration-[320ms] hover:bg-night-2"
        >
          Accept
        </button>
        <button
          onClick={() => choose('denied')}
          className="rounded-full border border-night px-4 py-2 font-mono text-[0.72rem] tracking-[0.08em] uppercase transition-colors duration-[320ms] hover:bg-paper"
        >
          Decline
        </button>
      </div>
    </div>
  )
}

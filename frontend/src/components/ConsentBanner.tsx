import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { clarityConfigured, getConsent, setConsent } from '@/analytics'

/**
 * Consent for the optional cookie-based tool (Clarity). Accept and Decline are equally easy,
 * as GDPR/LGPD require; nothing cookie-based loads before "Accept".
 */
export function ConsentBanner() {
  const [open, setOpen] = useState(() => clarityConfigured() && getConsent() === null)
  const [more, setMore] = useState(false)

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
  const btn =
    'rounded-full px-3 py-1.5 font-mono text-[0.66rem] tracking-[0.08em] uppercase transition-colors duration-[320ms]'
  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie choice"
      className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-xl rounded-lg border border-rule bg-stone/95 px-3.5 py-2.5 shadow-[0_12px_30px_-18px_rgba(12,16,24,0.45)] backdrop-blur sm:inset-x-6"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="min-w-0 flex-1 text-[12.5px] leading-snug text-earth">
          Allow analytics cookies to help improve this site?{' '}
          <button
            type="button"
            aria-expanded={more}
            aria-controls="consent-more"
            onClick={() => setMore((v) => !v)}
            className="whitespace-nowrap underline underline-offset-2 hover:text-night"
          >
            {more ? 'Read less' : 'Read more'}
          </button>
        </p>
        <div className="flex shrink-0 gap-1.5">
          <button onClick={() => choose('granted')} className={`${btn} bg-night text-stone hover:bg-night-2`}>
            Accept
          </button>
          <button onClick={() => choose('denied')} className={`${btn} border border-night hover:bg-paper`}>
            Decline
          </button>
        </div>
      </div>
      {more && (
        <p id="consent-more" className="mt-2 border-t border-dashed border-dash pt-2 text-[12px] leading-snug text-earth">
          Visits are always counted anonymously, without cookies. If you accept, Microsoft Clarity also records how
          pages are used (clicks and scrolling, never what you type) so I can see what is confusing. You can change this
          anytime in “Cookie settings” at the bottom of the page.{' '}
          <Link to="/privacy" className="underline underline-offset-2 hover:text-night">
            Privacy details
          </Link>
        </p>
      )}
    </div>
  )
}

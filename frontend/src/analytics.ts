/**
 * Visitor analytics, privacy-first.
 *
 * - Umami (cookieless, anonymous, aggregated): always on. No cookies or personal data, so no
 *   consent needed. Counts visits, pages, referrers, countries, devices and the events below.
 * - Microsoft Clarity (session recordings, heatmaps): uses cookies, so it only loads AFTER the
 *   visitor clicks "Accept" in the banner. Declining keeps only Umami.
 *
 * Both IDs are public (they appear in the page anyway) and live in frontend/.env.production.
 * If an ID is empty, that tool simply never loads, and the banner only appears when Clarity is
 * configured (no point asking otherwise).
 */

declare global {
  interface Window {
    umami?: { track: (event: string, data?: Record<string, string | number | boolean>) => void }
    clarity?: ((...args: unknown[]) => void) & { q?: unknown[] }
  }
}

const UMAMI_ID = import.meta.env.VITE_UMAMI_WEBSITE_ID as string | undefined
const UMAMI_SRC = (import.meta.env.VITE_UMAMI_SCRIPT_URL as string | undefined) || 'https://cloud.umami.is/script.js'
const CLARITY_ID = import.meta.env.VITE_CLARITY_PROJECT_ID as string | undefined

const KEY = 'analytics-consent' // remembering the choice itself is strictly necessary
export type Consent = 'granted' | 'denied' | null

export const clarityConfigured = () => !!CLARITY_ID

export function getConsent(): Consent {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'granted' || v === 'denied' ? v : null
  } catch {
    return null
  }
}

function addScript(src: string, attrs: Record<string, string> = {}) {
  const s = document.createElement('script')
  s.async = true
  s.src = src
  for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v)
  document.head.appendChild(s)
}

let umamiLoaded = false
function loadUmami() {
  if (umamiLoaded || !UMAMI_ID) return
  umamiLoaded = true
  addScript(UMAMI_SRC, { defer: '', 'data-website-id': UMAMI_ID })
}

let clarityLoaded = false
function loadClarity() {
  if (clarityLoaded || !CLARITY_ID) return
  clarityLoaded = true
  // Official Clarity bootstrap: queue calls until the tag script arrives.
  const c = function (...args: unknown[]) {
    ;(c.q = c.q || []).push(args)
  } as NonNullable<Window['clarity']>
  window.clarity = window.clarity || c
  addScript(`https://www.clarity.ms/tag/${CLARITY_ID}`)
  // Consent signal (required by Clarity for visitors in the EEA, UK and Switzerland).
  window.clarity('consentv2', { ad_Storage: 'denied', analytics_Storage: 'granted' })
}

/** Call once at startup. */
export function initAnalytics() {
  loadUmami()
  if (getConsent() === 'granted') loadClarity()
  const ref = new URLSearchParams(window.location.search).get('ref')
  if (ref) {
    // record which shared link brought the visitor (e.g. ?ref=linkedin-post1)
    const send = () => track('arrived-from-link', { ref: ref.slice(0, 60) })
    if (window.umami) send()
    else window.setTimeout(send, 1500)
  }
}

export function setConsent(choice: 'granted' | 'denied') {
  try {
    localStorage.setItem(KEY, choice)
  } catch {
    /* private mode: the choice just isn't remembered */
  }
  if (choice === 'granted') loadClarity()
  else if (clarityLoaded) {
    window.clarity?.('consentv2', { ad_Storage: 'denied', analytics_Storage: 'denied' })
    // drop Clarity's cookies and reload without it
    for (const name of ['_clck', '_clsk', 'CLID', 'ANONCHK', 'MR', 'MUID', 'SM']) {
      document.cookie = `${name}=; Max-Age=0; path=/`
    }
    window.location.reload()
  }
  track('consent', { choice })
}

export function resetConsent() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event('analytics-consent-reset'))
}

/** Custom event, sent to Umami (always) and Clarity (when consented). */
export function track(event: string, data?: Record<string, string | number | boolean>) {
  try {
    window.umami?.track(event, data)
    if (clarityLoaded) window.clarity?.('event', event)
  } catch {
    /* analytics must never break the site */
  }
}

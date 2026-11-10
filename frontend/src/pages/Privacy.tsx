import { SectionTitle } from '@/components/core'
import { clarityConfigured, getConsent, resetConsent } from '@/analytics'

export default function Privacy() {
  const consent = getConsent()
  return (
    <article className="max-w-2xl space-y-6 text-[15px] leading-relaxed">
      <SectionTitle eyebrow="What this site collects">Privacy</SectionTitle>
      <p>
        This is a personal portfolio project. I want to know how people use it, so I collect as little as possible and
        nothing that identifies you.
      </p>
      <h3 className="wide text-base font-extrabold uppercase">Always on: anonymous visit counts (Umami)</h3>
      <p className="text-earth">
        No cookies and no personal data. It records which pages are opened, the site you came from, your country,
        device type and browser, and a few actions (opening a race, switching between forecasts, searching a driver).
        Data is aggregated; I cannot tell who you are.
      </p>
      <h3 className="wide text-base font-extrabold uppercase">Only if you accept: Microsoft Clarity</h3>
      <p className="text-earth">
        Sets cookies and records how pages are used — clicks, scrolling and mouse movement — as replays and heatmaps.
        Text you type is masked. It helps me find what is confusing. It never loads unless you click “Accept”.
        Microsoft’s privacy statement applies to that data.
      </p>
      <h3 className="wide text-base font-extrabold uppercase">Your choice</h3>
      <p className="text-earth">
        {clarityConfigured()
          ? `Current choice: ${consent === 'granted' ? 'accepted' : consent === 'denied' ? 'declined' : 'not made yet'}.`
          : 'Clarity is not enabled on this site right now.'}
      </p>
      {clarityConfigured() && (
        <button
          onClick={resetConsent}
          className="rounded-full border border-night px-4 py-2 font-mono text-[0.72rem] tracking-[0.08em] uppercase hover:bg-paper"
        >
          Change cookie settings
        </button>
      )}
      <p className="text-earth">
        Questions or removal requests: contact me on{' '}
        <a className="underline underline-offset-2" href="https://www.linkedin.com/in/eduardo-costal">
          LinkedIn
        </a>
        .
      </p>
    </article>
  )
}

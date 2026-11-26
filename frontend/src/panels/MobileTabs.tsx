// ABOUTME: Bottom tab bar for phones: Moon (globe), Sites (lists and coordinates), Analysis (site panel)
// ABOUTME: Owner: Gian. Hidden on wide screens by CSS; App shows one section at a time from the tab

/** The section shown on a phone; wide screens show everything. */
export type MobileTab = 'globe' | 'sites' | 'analysis'

const TABS: { id: MobileTab; label: string; icon: React.ReactNode }[] = [
  {
    id: 'globe',
    label: 'Moon',
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
        <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="7.5" cy="8" r="1.4" fill="currentColor" />
        <circle cx="12.5" cy="12" r="1.1" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: 'sites',
    label: 'Sites',
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
        <path d="M10 17s5-4.6 5-8.5a5 5 0 1 0-10 0C5 12.4 10 17 10 17Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="10" cy="8.5" r="1.8" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: 'analysis',
    label: 'Analysis',
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
        <path d="M3.5 16.5h13M5.5 13.5V10M10 13.5V5.5M14.5 13.5V8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
]

/** The tab bar; `unseen` puts a dot on Analysis when a new result waits there. */
export function MobileTabs(props: { tab: MobileTab; unseen: boolean; onTab: (tab: MobileTab) => void }) {
  const { tab, unseen, onTab } = props
  return (
    <nav className="mobile-tabs" aria-label="Sections">
      {TABS.map((item) => (
        <button
          key={item.id}
          className={tab === item.id ? 'active' : undefined}
          aria-current={tab === item.id ? 'page' : undefined}
          onClick={() => onTab(item.id)}
        >
          <span className="mobile-tab-icon">
            {item.icon}
            {item.id === 'analysis' && unseen && <i className="mobile-tab-dot" aria-label="New result" />}
          </span>
          {item.label}
        </button>
      ))}
    </nav>
  )
}

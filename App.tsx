import { useEffect, useMemo, useState } from 'react'

type Tab = 'overview' | 'leads' | 'inbox' | 'analytics' | 'workflows' | 'settings'

type Lead = {
  id: string
  name: string
  phone: string
  service: string
  urgency: 'Low' | 'Medium' | 'High' | 'Emergency'
  source: string
  city: string
  status: 'New' | 'Qualified' | 'Booked' | 'Escalated' | 'Lost'
  lastUpdate: string
}

type Message = {
  role: 'AI' | 'Lead' | 'Human'
  text: string
  time: string
}

type Conversation = {
  id: string
  leadName: string
  tag: string
  status: string
  messages: Message[]
}

type Snapshot = {
  new_leads: number
  missed_calls: number
  responded_under_1_minute: number
  qualified_leads: number
  booking_links_sent: number
  booked_opportunities: number
  escalations: number
  lost_leads: number
}

const tabs: { id: Tab; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: '◎' },
  { id: 'leads', label: 'Leads', icon: '◫' },
  { id: 'inbox', label: 'Inbox', icon: '✉' },
  { id: 'analytics', label: 'Analytics', icon: '▣' },
  { id: 'workflows', label: 'Workflows', icon: '⇄' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

const pipeline: Lead[] = [
  { id: 'L-1029', name: 'Amelia Ross', phone: '(480) 555-1839', service: 'AC repair', urgency: 'High', source: 'Missed call', city: 'Mesa', status: 'Booked', lastUpdate: '2 min ago' },
  { id: 'L-1028', name: 'Brandon Lee', phone: '(480) 555-2201', service: 'No cooling', urgency: 'Emergency', source: 'After-hours SMS', city: 'Tempe', status: 'Escalated', lastUpdate: '4 min ago' },
  { id: 'L-1027', name: 'Kara Benson', phone: '(602) 555-4488', service: 'Maintenance', urgency: 'Low', source: 'Web form', city: 'Phoenix', status: 'Qualified', lastUpdate: '17 min ago' },
  { id: 'L-1026', name: 'Drew Patel', phone: '(480) 555-0982', service: 'Heat pump install', urgency: 'Medium', source: 'Inbound SMS', city: 'Gilbert', status: 'New', lastUpdate: '22 min ago' },
  { id: 'L-1025', name: 'Zoe Watkins', phone: '(602) 555-0091', service: 'Thermostat issue', urgency: 'Low', source: 'Missed call', city: 'Scottsdale', status: 'Lost', lastUpdate: '36 min ago' },
]

const conversations: Conversation[] = [
  {
    id: 'C-41',
    leadName: 'Amelia Ross',
    tag: 'Booked',
    status: 'Cooling repair',
    messages: [
      { role: 'AI', text: 'Hi, this is CallSpark AI for Desert Peak HVAC. Sorry we missed your call. Are you needing repair, installation, or maintenance?', time: '9:02 AM' },
      { role: 'Lead', text: 'Repair. AC is blowing warm air.', time: '9:03 AM' },
      { role: 'AI', text: 'Got it. Is this urgent, or can it wait until normal business hours?', time: '9:03 AM' },
      { role: 'Lead', text: 'Pretty urgent. We have kids at home.', time: '9:04 AM' },
      { role: 'AI', text: 'Thanks. What city is the job in?', time: '9:04 AM' },
      { role: 'Lead', text: 'Mesa.', time: '9:05 AM' },
      { role: 'AI', text: 'Thanks, Amelia. I have enough to route this now. I have sent your info to the team and a booking link.', time: '9:05 AM' },
    ],
  },
  {
    id: 'C-40',
    leadName: 'Brandon Lee',
    tag: 'Escalated',
    status: 'Emergency triage',
    messages: [
      { role: 'AI', text: 'Thanks for contacting Desert Peak HVAC. Is this an emergency?', time: '8:48 AM' },
      { role: 'Lead', text: 'No cooling at all and my elderly dad is here.', time: '8:48 AM' },
      { role: 'AI', text: 'I am escalating this now so the on-call team can respond quickly.', time: '8:49 AM' },
      { role: 'Human', text: 'Dispatcher notified and callback sent.', time: '8:50 AM' },
    ],
  },
]

const chartDays = [
  { day: 'Mon', leads: 12, booked: 5 },
  { day: 'Tue', leads: 15, booked: 7 },
  { day: 'Wed', leads: 11, booked: 4 },
  { day: 'Thu', leads: 18, booked: 8 },
  { day: 'Fri', leads: 20, booked: 10 },
  { day: 'Sat', leads: 9, booked: 3 },
  { day: 'Sun', leads: 7, booked: 3 },
]

const serviceMix = [
  { label: 'Repair', value: 42 },
  { label: 'Install', value: 24 },
  { label: 'Maintenance', value: 21 },
  { label: 'Other', value: 13 },
]

function StatCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card stat-card">
      <div className="muted small">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="muted tiny">{note}</div>
    </div>
  )
}

function MiniBars() {
  const max = Math.max(...chartDays.map((d) => d.leads))
  return (
    <div className="bars">
      {chartDays.map((d) => (
        <div className="bar-col" key={d.day}>
          <div className="bar-stack">
            <div className="bar lead-bar" style={{ height: `${(d.leads / max) * 100}%` }} />
            <div className="bar booked-bar" style={{ height: `${(d.booked / max) * 100}%` }} />
          </div>
          <span className="tiny muted">{d.day}</span>
        </div>
      ))}
    </div>
  )
}

function Donut() {
  const cumulative = serviceMix.reduce<number[]>((acc, item, index) => {
    const prev = index === 0 ? 0 : acc[index - 1]
    acc.push(prev + item.value)
    return acc
  }, [])
  const gradient = serviceMix
    .map((item, index) => {
      const start = index === 0 ? 0 : cumulative[index - 1]
      const end = cumulative[index]
      return `var(--accent-${index + 1}) ${(start / 100) * 100}% ${(end / 100) * 100}%`
    })
    .join(', ')

  return (
    <div className="donut-wrap">
      <div className="donut" style={{ background: `conic-gradient(${gradient})` }}>
        <div className="donut-inner">
          <div className="tiny muted">Booked rate</div>
          <div className="stat-value">38%</div>
        </div>
      </div>
      <div className="legend">
        {serviceMix.map((item, i) => (
          <div className="legend-row" key={item.label}>
            <span className={`legend-dot legend-${i + 1}`} />
            <span>{item.label}</span>
            <strong>{item.value}%</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [selectedConversation, setSelectedConversation] = useState(conversations[0])

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE_URL
    if (!apiBase) return
    fetch(`${apiBase}/internal/report/daily`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('bad response'))))
      .then((data) => setSnapshot(data))
      .catch(() => setSnapshot(null))
  }, [])

  const headlineStats = useMemo(() => {
    const source = snapshot ?? {
      new_leads: 48,
      missed_calls: 17,
      responded_under_1_minute: 44,
      qualified_leads: 29,
      booking_links_sent: 22,
      booked_opportunities: 18,
      escalations: 6,
      lost_leads: 5,
    }

    return {
      leads: source.new_leads,
      booked: source.booked_opportunities,
      responseRate: `${Math.round((source.responded_under_1_minute / Math.max(source.new_leads, 1)) * 100)}%`,
      recovery: `$${(source.booked_opportunities * 340).toLocaleString()}`,
    }
  }, [snapshot])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand-badge">⚡</div>
          <div className="brand-name">CallSpark AI</div>
          <div className="muted tiny">Revenue recovery for HVAC teams</div>
        </div>
        <nav className="nav-list">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`nav-item ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
        <div className="card sidebar-card">
          <div className="muted small">Deployment status</div>
          <div className="status-pill ok">Frontend ready</div>
          <div className="status-pill">API {snapshot ? 'connected' : 'demo mode'}</div>
        </div>
      </aside>

      <main className="main-pane">
        <header className="topbar">
          <div>
            <div className="eyebrow">Live workspace</div>
            <h1>{activeTab === 'overview' ? 'Operations cockpit' : tabs.find((t) => t.id === activeTab)?.label}</h1>
          </div>
          <div className="top-actions">
            <button className="ghost-btn">Export report</button>
            <button className="primary-btn">Book demo</button>
          </div>
        </header>

        {activeTab === 'overview' && (
          <section className="page-grid">
            <div className="stats-grid">
              <StatCard label="New leads" value={String(headlineStats.leads)} note="Across calls, SMS, and forms" />
              <StatCard label="Booked opportunities" value={String(headlineStats.booked)} note="Qualified and routed" />
              <StatCard label="Response under 1 min" value={headlineStats.responseRate} note="AI speed to lead" />
              <StatCard label="Revenue influenced" value={headlineStats.recovery} note="Estimated booked value" />
            </div>
            <div className="card hero-card">
              <div>
                <div className="eyebrow">What CallSpark does</div>
                <h2>AI receptionist, missed-call recovery, and lead routing in one place.</h2>
                <p className="muted">
                  Handle after-hours leads, qualify inbound jobs, escalate emergencies, and surface clean analytics for owners and dispatchers.
                </p>
              </div>
              <div className="hero-grid">
                <div className="hero-metric">
                  <span className="muted tiny">Escalations today</span>
                  <strong>6</strong>
                </div>
                <div className="hero-metric">
                  <span className="muted tiny">Booking links sent</span>
                  <strong>22</strong>
                </div>
                <div className="hero-metric">
                  <span className="muted tiny">Lost leads</span>
                  <strong>5</strong>
                </div>
                <div className="hero-metric">
                  <span className="muted tiny">Best source</span>
                  <strong>Missed call SMS</strong>
                </div>
              </div>
            </div>
            <div className="card">
              <div className="section-head">
                <div>
                  <h3>Lead momentum</h3>
                  <p className="muted small">New leads vs booked opportunities</p>
                </div>
                <span className="status-pill ok">7 days</span>
              </div>
              <MiniBars />
            </div>
            <div className="card">
              <div className="section-head">
                <div>
                  <h3>Service mix</h3>
                  <p className="muted small">What the AI is qualifying most</p>
                </div>
              </div>
              <Donut />
            </div>
            <div className="card wide-card">
              <div className="section-head">
                <div>
                  <h3>Recent pipeline</h3>
                  <p className="muted small">Fast view of active leads</p>
                </div>
              </div>
              <table className="lead-table">
                <thead>
                  <tr>
                    <th>Lead</th>
                    <th>Service</th>
                    <th>Urgency</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Last update</th>
                  </tr>
                </thead>
                <tbody>
                  {pipeline.map((lead) => (
                    <tr key={lead.id}>
                      <td>
                        <div className="lead-name">{lead.name}</div>
                        <div className="muted tiny">{lead.phone}</div>
                      </td>
                      <td>{lead.service}</td>
                      <td><span className={`chip ${lead.urgency.toLowerCase()}`}>{lead.urgency}</span></td>
                      <td>{lead.source}</td>
                      <td><span className="status-pill">{lead.status}</span></td>
                      <td>{lead.lastUpdate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeTab === 'leads' && (
          <section className="card page-card">
            <div className="section-head">
              <div>
                <h3>Lead pipeline</h3>
                <p className="muted small">All incoming opportunities with routing status</p>
              </div>
              <button className="ghost-btn">New filter</button>
            </div>
            <div className="filters">
              <span className="filter-chip active">All</span>
              <span className="filter-chip">Missed calls</span>
              <span className="filter-chip">Emergency</span>
              <span className="filter-chip">Booked</span>
              <span className="filter-chip">Lost</span>
            </div>
            <table className="lead-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Service</th>
                  <th>City</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {pipeline.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.id}</td>
                    <td>{lead.name}</td>
                    <td>{lead.service}</td>
                    <td>{lead.city}</td>
                    <td>{lead.source}</td>
                    <td><span className="status-pill">{lead.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {activeTab === 'inbox' && (
          <section className="inbox-layout">
            <div className="card inbox-list">
              <div className="section-head">
                <div>
                  <h3>Conversations</h3>
                  <p className="muted small">AI, lead, and human handoff thread</p>
                </div>
              </div>
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  className={`conversation-preview ${selectedConversation.id === conversation.id ? 'selected' : ''}`}
                  onClick={() => setSelectedConversation(conversation)}
                >
                  <div>
                    <strong>{conversation.leadName}</strong>
                    <div className="muted tiny">{conversation.status}</div>
                  </div>
                  <span className="status-pill">{conversation.tag}</span>
                </button>
              ))}
            </div>
            <div className="card conversation-panel">
              <div className="section-head">
                <div>
                  <h3>{selectedConversation.leadName}</h3>
                  <p className="muted small">{selectedConversation.status}</p>
                </div>
                <button className="ghost-btn">Escalate</button>
              </div>
              <div className="thread">
                {selectedConversation.messages.map((message, index) => (
                  <div key={`${message.time}-${index}`} className={`bubble-row ${message.role === 'Lead' ? 'lead-row' : ''}`}>
                    <div className={`bubble ${message.role.toLowerCase()}`}>
                      <div className="tiny muted">{message.role} • {message.time}</div>
                      <div>{message.text}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'analytics' && (
          <section className="page-grid">
            <div className="card">
              <div className="section-head">
                <div>
                  <h3>Weekly performance</h3>
                  <p className="muted small">Core metrics owners care about</p>
                </div>
              </div>
              <MiniBars />
            </div>
            <div className="card">
              <div className="section-head">
                <div>
                  <h3>Conversion levers</h3>
                  <p className="muted small">Where the AI is helping most</p>
                </div>
              </div>
              <ul className="metric-list">
                <li><span>Missed-call recovery rate</span><strong>67%</strong></li>
                <li><span>Qualified-to-booked</span><strong>62%</strong></li>
                <li><span>After-hours capture</span><strong>81%</strong></li>
                <li><span>Emergency escalation speed</span><strong>1.8 min</strong></li>
              </ul>
            </div>
            <div className="card wide-card">
              <div className="section-head">
                <div>
                  <h3>Executive summary</h3>
                  <p className="muted small">Simple talking points for the client</p>
                </div>
              </div>
              <div className="summary-grid">
                <div className="summary-box">
                  <span className="eyebrow">Biggest win</span>
                  <strong>After-hours leads are converting better than voicemail.</strong>
                  <p className="muted small">The instant text-back flow is the highest-performing automation.</p>
                </div>
                <div className="summary-box">
                  <span className="eyebrow">Risk</span>
                  <strong>Install requests are stalling when pricing questions show up too early.</strong>
                  <p className="muted small">Route those faster to a human or soften the script.</p>
                </div>
                <div className="summary-box">
                  <span className="eyebrow">Next test</span>
                  <strong>Shorten first response by one question.</strong>
                  <p className="muted small">Goal: improve reply rate on non-emergency repair leads.</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'workflows' && (
          <section className="page-grid">
            <div className="card workflow-card">
              <h3>Active automations</h3>
              <div className="workflow-list">
                <div className="workflow-item"><strong>Missed-call text back</strong><span className="status-pill ok">Live</span></div>
                <div className="workflow-item"><strong>After-hours triage</strong><span className="status-pill ok">Live</span></div>
                <div className="workflow-item"><strong>Emergency escalation</strong><span className="status-pill ok">Live</span></div>
                <div className="workflow-item"><strong>Booking link handoff</strong><span className="status-pill">Testing</span></div>
              </div>
            </div>
            <div className="card workflow-card">
              <h3>Flow outline</h3>
              <ol className="flow-list">
                <li>Lead enters from call, SMS, or form.</li>
                <li>AI sends first response in under 60 seconds.</li>
                <li>Collects service, urgency, location, and callback preference.</li>
                <li>Applies hard rules for emergency and handoff.</li>
                <li>Logs everything and updates reporting.</li>
              </ol>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="page-grid">
            <div className="card settings-card">
              <h3>Workspace</h3>
              <div className="settings-list">
                <div><span className="muted small">Brand</span><strong>CallSpark AI</strong></div>
                <div><span className="muted small">Primary vertical</span><strong>HVAC</strong></div>
                <div><span className="muted small">API base URL</span><strong>{import.meta.env.VITE_API_BASE_URL || 'Demo mode'}</strong></div>
                <div><span className="muted small">Data source</span><strong>{snapshot ? 'Live backend snapshot' : 'Local mock data'}</strong></div>
              </div>
            </div>
            <div className="card settings-card">
              <h3>Publish checklist</h3>
              <ul className="check-list">
                <li>Upload repo to GitHub</li>
                <li>Deploy frontend to Vercel</li>
                <li>Set VITE_API_BASE_URL</li>
                <li>Deploy backend to Render or Railway</li>
                <li>Point Twilio webhooks at backend</li>
              </ul>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default App

/**
 * Public website (CMD-026): what UrbanTransit IQ is, what it finds and how, for anyone who
 * opens the site before signing in. Content follows the SRS (1.1 background, 1.2 proposed
 * solution and the list of what the application must identify, the two pipelines, the
 * recommendation engine, the four roles). Every number comes from GET /api/public/summary,
 * which serves network-level totals only; nothing on this page is typed in by hand.
 *
 * Motion: hero enters once, sections reveal on scroll in reading order, CTAs and images give
 * hover/press feedback. All of it is transform/opacity and follows the reduced-motion tiers.
 */

import {
 ArrowRight, ChartLineUp, Clock, Cpu, Database, FlowArrow, GitBranch, Lightbulb, MapTrifold, ShieldCheck,
 Sparkle, TrendUp, UsersThree, Warning,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import { motion, useReducedMotion } from 'motion/react'
import { Link } from 'react-router-dom'
import { CountUp, Reveal, StaggerScope } from '../components/motion'
import { useApi } from '../lib/useApi'

interface PublicSummary {
 network: { routes: number; stops: number; vehicles: number }
 service: { first_day: string | null; last_day: string | null; avg_daily_boardings: number | null }
 route_classes: Record<string, number>
 recommendations: { total: number; by_priority: Record<string, number> }
 pipeline_agreement: number | null
 comparison_cases: number
 models: { task: string; algorithm: string; accuracy?: number | null; macro_f1?: number | null; mae?: number | null; r2?: number | null }[]
}

const whole = (n: number) => Math.round(n).toLocaleString()
const monthYear = (d: string | null | undefined) => (d ? new Date(`${d}T12:00:00`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' }) : '')
const EASE = [0.16, 1, 0.3, 1] as const

const FINDS: { icon: Icon; title: string; body: string; wide?: boolean }[] = [
 { icon: Clock, title: 'Peak periods', body: 'Morning, evening, weekend and route-specific peaks, found from actual demand rather than fixed time slots.', wide: true },
 { icon: UsersThree, title: 'Overcrowding that repeats', body: 'Separates routes that overload day after day from a single busy trip.' },
 { icon: Warning, title: 'Delays and bottlenecks', body: 'Delay patterns by route, stop, hour and vehicle, and the stops where delays build up.' },
 { icon: TrendUp, title: 'Underused services', body: 'Periods running far below capacity, where frequency or vehicle size could come down.', wide: true },
 { icon: FlowArrow, title: 'Passenger flows', body: 'Where people board and alight, and the busiest origin-destination pairs.', wide: true },
 { icon: ChartLineUp, title: 'Demand ahead', body: 'Daily demand forecasts per route, checked against a simple baseline.' },
]

const STEPS: { icon: Icon; title: string; body: string }[] = [
 { icon: Database, title: 'A year of generated operations', body: 'Tickets, trips, schedules, passenger counts, delays and GPS pings for a full network, with realistic defects built in.' },
 { icon: Cpu, title: 'Stored and cleaned at scale', body: 'Raw files land in HDFS; Spark validates every record, quarantines bad ones with a documented rule, and writes Parquet.' },
 { icon: MapTrifold, title: 'Analysed with Spark SQL', body: 'Features per trip, route and stop feed the scores: performance, reliability, crowding, flows and anomalies.' },
 { icon: GitBranch, title: 'Modelled twice, independently', body: 'Spark MLlib and a separate Python pipeline train on the same data; their answers are compared case by case.' },
 { icon: Lightbulb, title: 'Turned into actions', body: 'A rule-based engine proposes service changes with the evidence behind each; a what-if tool estimates their effect.' },
]

const ROLES: { title: string; body: string }[] = [
 { title: 'Operators', body: 'Daily dashboards, predictions, what-if scenarios and recommendations for the routes they run.' },
 { title: 'Analysts', body: 'Every analysis table with filters and CSV export, model evidence and forecasts.' },
 { title: 'Administrators', body: 'Routes, stops, vehicles, user accounts and roles, the audit trail and model training.' },
 { title: 'Evaluators', body: 'Read access to results, evidence, predictions and the audit trail, to check the work.' },
]

const PRINCIPLES = [
 'Every model figure is labelled an estimate and names the model, its version and its test score.',
 'The network map replays recorded GPS data and always shows the replayed date; nothing is presented as live.',
 'Predictions and recommendations come from our own pipelines and rules, never from a generative AI service.',
 'Passenger records stay inside the analysis; this page and the dashboards show totals, not people.',
]

function Shot({ src, alt, className = '' }: { src: string; alt: string; className?: string }) {
 return (
  <figure className={`site-shot ${className}`}>
   <img src={src} alt={alt} loading="lazy" decoding="async" width={1400} height={900} />
  </figure>
 )
}

export function WelcomePage() {
 const summary = useApi<PublicSummary>('/public/summary')
 const s = summary.data
 const reduce = useReducedMotion()
 const crowding = s?.models.find((m) => m.task === 'crowding_flag')
 const demand = s?.models.find((m) => m.task === 'daily_boardings')
 const delay = s?.models.find((m) => m.task === 'delay_severity')

 const enter = (delay: number) => ({
  initial: reduce ? { opacity: 0 } : { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: reduce ? { duration: 0.15 } : { duration: 0.6, delay, ease: EASE },
 })

 return (
  <div className="site">
   <header className="site-nav">
    <Link to="/welcome" className="site-brand"><img src="/logo-64.png" alt="" width={36} height={36} />UrbanTransit IQ</Link>
    <nav aria-label="Sections">
     <a href="#finds">What it finds</a>
     <a href="#how">How it works</a>
     <a href="#models">Models</a>
     <a href="#roles">Who it is for</a>
    </nav>
    <Link className="btn" to="/login">Sign in</Link>
   </header>

   <main id="main">
    <section className="site-hero">
     <div className="site-hero-copy">
      <motion.h1 {...enter(0)}>Bus data, turned into service decisions.</motion.h1>
      <motion.p {...enter(0.08)}>
       A year of trips, passenger counts and delays, analysed to show where service falls short and what to change.
      </motion.p>
      <motion.div className="site-cta" {...enter(0.16)}>
       <Link className="btn" to="/login">Sign in <ArrowRight size={16} weight="bold" aria-hidden="true" /></Link>
       <a className="btn btn-quiet" href="#finds">See what it finds</a>
      </motion.div>
     </div>
     <motion.div className="site-hero-visual" {...enter(0.12)}>
      <Shot src="/site/overview.webp" alt="The network overview dashboard: route scores, ridership and the route map." />
      <img className="site-hero-logo" src="/logo-192.png" alt="" width={112} height={112} />
     </motion.div>
    </section>

    <StaggerScope>
     <section className="site-strip" aria-label="The network in numbers">
      {[
       { label: 'Routes', value: s?.network.routes },
       { label: 'Stops', value: s?.network.stops },
       { label: 'Vehicles', value: s?.network.vehicles },
       { label: 'Boardings per day', value: s?.service.avg_daily_boardings ?? undefined },
       { label: 'Recommendations', value: s?.recommendations.total },
      ].map((k) => (
       <Reveal key={k.label} className="site-kpi">
        <span className="site-kpi-value">{k.value != null ? <CountUp value={k.value} format={whole} /> : '…'}</span>
        <span className="site-kpi-label">{k.label}</span>
       </Reveal>
      ))}
      <p className="site-strip-note">
       {s ? `From the loaded data, ${monthYear(s.service.first_day)} to ${monthYear(s.service.last_day)}.` : summary.error ? 'Figures are unavailable while the service is offline.' : 'Loading the figures…'}
      </p>
     </section>

     <section id="finds" className="site-section">
      <Reveal className="site-head">
       <h2>What it finds</h2>
       <p>The questions a transport operator asks every week, answered from the data rather than a spreadsheet.</p>
      </Reveal>
      <div className="site-bento">
       {FINDS.map((f) => {
        const Glyph = f.icon
        return (
         <Reveal key={f.title} as="article" className={`site-tile ${f.wide ? 'wide' : ''}`}>
          <span className="site-tile-icon" aria-hidden="true"><Glyph size={22} weight="duotone" /></span>
          <h3>{f.title}</h3>
          <p>{f.body}</p>
         </Reveal>
        )
       })}
      </div>
     </section>

     <section id="how" className="site-section site-how">
      <Reveal className="site-head">
       <h2>How it works</h2>
       <p>One pipeline from raw records to recommendations, built on the Hadoop ecosystem and Python.</p>
      </Reveal>
      <div className="site-steps">
       {STEPS.map((st, i) => {
        const Glyph = st.icon
        return (
         <Reveal key={st.title} as="div" className="site-step">
          <span className="site-step-no" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
          <span className="site-step-icon" aria-hidden="true"><Glyph size={20} weight="duotone" /></span>
          <div><h3>{st.title}</h3><p>{st.body}</p></div>
         </Reveal>
        )
       })}
      </div>
     </section>

     <section id="models" className="site-section site-split">
      <Reveal className="site-split-copy">
       <h2>Two pipelines, one answer you can check</h2>
       <p>Spark MLlib and an independent Python pipeline model the same problems. Where they agree, the answer is
        stronger; where they disagree, the comparison shows why.</p>
       <dl className="site-facts">
        <div><dt>Crowding risk, unseen trips</dt><dd>{crowding?.accuracy != null ? `${(crowding.accuracy * 100).toFixed(1)}% accurate` : '…'}</dd></div>
        <div><dt>Daily demand error</dt><dd>{demand?.mae != null ? `${whole(demand.mae)} boardings per route-day` : '…'}</dd></div>
        <div><dt>Spark and Python agree</dt><dd>{s?.pipeline_agreement != null ? `${(s.pipeline_agreement * 100).toFixed(1)}% of ${s.comparison_cases.toLocaleString()} cases` : '…'}</dd></div>
       </dl>
       {delay?.accuracy != null && (
        <p className="site-honest"><Sparkle size={14} weight="fill" aria-hidden="true" /> Delay-severity prediction is still below its
         accuracy target ({(delay.accuracy * 100).toFixed(1)}%), and the dashboard says so next to every delay answer.</p>
       )}
      </Reveal>
      <Reveal className="site-split-visual">
       <Shot src="/site/forecast.webp" alt="The demand forecast page: observed boardings, model backtest and forecast." />
      </Reveal>
     </section>

     <section id="roles" className="site-section">
      <Reveal className="site-head">
       <h2>Who it is for</h2>
       <p>Four roles, each seeing what their work needs. Access is enforced by the server, not just hidden in the menu.</p>
      </Reveal>
      <div className="site-roles">
       {ROLES.map((r) => (
        <Reveal key={r.title} className="site-role"><h3>{r.title}</h3><p>{r.body}</p></Reveal>
       ))}
      </div>
     </section>

     <section className="site-section site-principles">
      <Reveal className="site-head">
       <h2><ShieldCheck size={26} weight="duotone" aria-hidden="true" /> Numbers you can trust</h2>
      </Reveal>
      <div className="site-principle-list">
       {PRINCIPLES.map((p) => <Reveal key={p} as="div" className="site-principle"><p>{p}</p></Reveal>)}
      </div>
     </section>
    </StaggerScope>
   </main>

   <footer className="site-footer">
    <div className="site-brand"><img src="/logo-64.png" alt="" width={28} height={28} />UrbanTransit IQ</div>
    <p>Built with Hadoop HDFS, Apache Spark, PySpark and Spark SQL, scikit-learn and XGBoost, Flask, MySQL and React.</p>
    <nav aria-label="Footer">
     <a href="https://github.com/wisamahmed851/UrbanTransit" target="_blank" rel="noreferrer">Source on GitHub</a>
     <Link to="/login">Sign in</Link>
    </nav>
   </footer>
  </div>
 )
}

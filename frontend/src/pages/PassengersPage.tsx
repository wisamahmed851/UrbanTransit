import { ChartFrame, HBarChart } from '../components/charts'
import { ErrorNotice, Loading, PageHead, Panel } from '../components/ui'
import { label, num, pct } from '../lib/format'
import { useRows } from '../lib/useApi'

export function PassengersPage() {
  const seg = useRows('segment_summary', { limit: 10, sort: '-card_holders' })
  const rows = seg.data?.rows ?? []
  const chart = rows.map((r) => ({ label: String(r.segment), value: Number(r.share_of_card_holders) }))

  return (
    <div className="page">
      <PageHead title="Passengers">
        Travel habits of registered smart-card holders, grouped by how often, when and how far they ride. Cash riders cannot
        be grouped, so these are shares of card holders, not of all passengers.
      </PageHead>
      {seg.error && <ErrorNotice error={seg.error} />}
      <Panel title="Card holders by travel pattern">
        {seg.loading && !seg.data ? <Loading /> : (
          <ChartFrame
            chart={<HBarChart name="Share of card holders" data={chart} format={(v) => pct(v, 0)} />}
            rows={rows}
            columns={[
              { key: 'segment', label: 'Pattern' },
              { key: 'card_holders', label: 'Card holders', num: true, render: (r) => num(r.card_holders) },
              { key: 'share_of_card_holders', label: 'Share of holders', num: true, render: (r) => pct(r.share_of_card_holders) },
              { key: 'share_of_est_journeys', label: 'Share of journeys', num: true, render: (r) => pct(r.share_of_est_journeys) },
              { key: 'avg_active_days_per_week', label: 'Days riding / week', num: true, render: (r) => num(r.avg_active_days_per_week, 1) },
              { key: 'avg_peak_share', label: 'Trips at peak', num: true, render: (r) => pct(r.avg_peak_share, 0) },
              { key: 'avg_journey_km', label: 'Average km', num: true, render: (r) => num(r.avg_journey_km, 1) },
              { key: 'most_common_passenger_type', label: 'Most common card', render: (r) => label(r.most_common_passenger_type) },
            ]}
          />
        )}
      </Panel>
      <Panel title="How the patterns are decided" note="Checked in this order; the first rule that fits wins.">
        <ol style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.3rem', fontSize: 'var(--fs-sm)', maxWidth: '70ch' }}>
          <li><b>Daily commuter</b>: rides on 3 or more days a week, 80%+ of journeys on weekdays.</li>
          <li><b>Weekend traveller</b>: half or more of journeys at weekends.</li>
          <li><b>Long-distance traveller</b>: average journey among the longest 20% of card holders.</li>
          <li><b>Peak-hour traveller</b>: 70%+ of journeys in the morning or evening peak.</li>
          <li><b>Occasional traveller</b>: everyone else.</li>
        </ol>
      </Panel>
    </div>
  )
}


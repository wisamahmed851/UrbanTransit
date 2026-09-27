import { useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import { ErrorNotice, PageHead, Panel, Status } from '../../components/ui'
import { useApi } from '../../lib/useApi'

interface JobRun { job_id: number; job_name: string; status: string; duration_seconds?: number | null }

const TRAINING_JOBS = ['spark_models', 'python_models', 'evaluate_saved_models', 'load_model_outputs']

/** Admin only (`models:train`). Training is heavy, so the API allows one run at a time. */
export function TrainPage() {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 3000)
    return () => clearInterval(id)
  }, [])
  const jobs = useApi<{ entries: JobRun[] }>('/jobs', { limit: 20, _: tick })

  const start = async (pipeline: 'spark' | 'python') => {
    if (!window.confirm(`Start ${pipeline === 'spark' ? 'Spark' : 'Python'} training? It reads the full dataset and can keep this computer busy for a long time.`)) return
    setBusy(true); setMessage(''); setError(null)
    try {
      const res = await api<{ message: string }>('/train', { method: 'POST', body: JSON.stringify({ pipeline }) })
      setMessage(res.message)
    } catch (e) {
      setError(e as ApiError)
    } finally {
      setBusy(false)
    }
  }

  const trainingJobs = (jobs.data?.entries ?? []).filter((j) => TRAINING_JOBS.includes(j.job_name))

  return (
    <div className="page">
      <PageHead title="Train models">
        Retrain the models on this server. Training reads the full dataset and can take a long time on a laptop; the
        usual path is to train on a stronger machine and copy the model files into models/ (see Retrain.md).
      </PageHead>

      <div className="grid-2">
        <Panel title="Spark MLlib pipeline" note="Starts HDFS if needed, trains the Phase 6 Spark models, then re-scores and reloads the served models.">
          <button className="btn" onClick={() => start('spark')} disabled={busy}>Start Spark training</button>
        </Panel>
        <Panel title="Python pipeline" note="Trains the Phase 7 Python models on the full training split, then re-scores and reloads the served models.">
          <button className="btn" onClick={() => start('python')} disabled={busy}>Start Python training</button>
        </Panel>
      </div>

      <div className="notice notice-warn" role="note">
        <strong>New models replace the current ones.</strong>
        <span>Training overwrites the saved model files whatever their scores. The re-scoring step that follows reports
          whether they meet the SRS targets (accuracy of at least 85% or macro F1 of at least 0.80); check Model results
          before relying on them.</span>
      </div>
      {message && <div className="notice notice-info" role="status"><span>{message}</span></div>}
      {error && <ErrorNotice error={error} />}

      <Panel title="Progress and logs" note="Recent training jobs, refreshed every 3 seconds.">
        {trainingJobs.length === 0 ? <p className="muted">No recent training jobs.</p> : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {trainingJobs.map((j) => <JobLog key={j.job_id} job={j} tick={tick} />)}
          </div>
        )}
      </Panel>
    </div>
  )
}

function JobLog({ job, tick }: { job: JobRun; tick: number }) {
  const running = job.status.toLowerCase() === 'running'
  // Poll the log while the job runs; once finished, fetch it once.
  const log = useApi<{ log: string }>(`/jobs/${job.job_id}/log`, running ? { _: tick } : undefined)
  const tone = job.status === 'success' ? 'good' : job.status === 'failed' ? 'critical' : 'neutral'
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'center', marginBottom: '0.4rem' }}>
        <strong>{job.job_name}</strong>
        <Status tone={tone}>{job.status}{job.duration_seconds ? ` (${job.duration_seconds}s)` : running ? ' (running)' : ''}</Status>
      </div>
      <pre className="job-log">{log.data?.log || 'Waiting for the log…'}</pre>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { PageHead, Panel } from '../../components/ui'
import { useAuth } from '../../auth/AuthContext'
import { useApi } from '../../lib/useApi'

export function TrainPage() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const { token } = useAuth()
  
  // Continuous progress polling
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 3000)
    return () => clearInterval(id)
  }, [])
  const jobs = useApi<{ entries: any[] }>('/jobs', { limit: 20, _: tick })
  
  const handleTrain = async (pipeline: string) => {
    setLoading(true)
    setMessage('')
    try {
      const res = await fetch('/api/train', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline })
      })
      const data = await res.json()
      setMessage(data.message || 'Started')
    } catch (e: any) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setTimeout(() => setLoading(false), 2000) // Small debounce
    }
  }

  // Filter jobs for training
  const trainingJobs = jobs.data?.entries.filter(j => 
    ['spark_models', 'python_models', 'evaluate_saved_models', 'load_model_outputs'].includes(j.job_name)
  ) || []

  return (
    <div className="page">
      <PageHead title="Train Models">Trigger ML training pipelines.</PageHead>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <Panel title="Spark MLlib Pipeline" className="train-panel">
          <p>This will:</p>
          <ul style={{ marginBottom: '1rem', minHeight: '80px' }}>
            <li>Start HDFS if not running</li>
            <li>Train Spark models</li>
            <li>Evaluate and load models</li>
          </ul>
          <div style={{ marginTop: '1rem' }}>
            <button className="btn btn-primary" onClick={() => handleTrain('spark')} disabled={loading}>
              Start Spark Training
            </button>
          </div>
        </Panel>

        <Panel title="Python Pipeline" className="train-panel">
          <p>This will:</p>
          <ul style={{ marginBottom: '1rem', minHeight: '80px' }}>
            <li>Train Python models with full data</li>
            <li>Evaluate and load models</li>
          </ul>
          <div style={{ marginTop: '1rem' }}>
            <button className="btn btn-primary" onClick={() => handleTrain('python')} disabled={loading}>
              Start Python Training
            </button>
          </div>
        </Panel>
      </div>

      <div style={{ marginTop: '1.5rem', background: 'var(--bg-alt)', padding: '1rem', borderRadius: '8px' }}>
        <strong>Evaluation Constraints:</strong> The newly trained models will be tested against the current Registry baseline. A new model will only be saved and utilized if it meets strict threshold constraints (e.g. Accuracy &gt;= 0.85 or Macro F1 &gt;= 0.80 for Crowding).
      </div>
      {message && <p style={{ marginTop: '1rem', color: 'var(--blue)', fontWeight: 'bold' }}>{message}</p>}

      <Panel title="Continuous Progress & Logs" className="progress-panel" style={{ marginTop: '2rem' }}>
        <p>Recent training job activity:</p>
        {trainingJobs.length === 0 ? <p style={{ color: 'var(--gray)' }}>No recent training jobs.</p> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
            {trainingJobs.map((j: any) => (
              <JobLogCard key={j.job_id} job={j} token={token} tick={tick} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}

function JobLogCard({ job, token, tick }: { job: any, token: string | null, tick: number }) {
  const [log, setLog] = useState<string>('')
  
  useEffect(() => {
    let active = true;
    const fetchLog = async () => {
      try {
        const res = await fetch(`/api/jobs/${job.job_id}/log`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        const data = await res.json()
        if (active) setLog(data.log || '')
      } catch (e) {
        console.error(e)
      }
    }

    if (String(job.status).toLowerCase() === 'running' || !log) {
      fetchLog()
    }
    
    return () => { active = false }
  }, [job.job_id, job.status, tick, token]) 

  const isSuccess = String(job.status).toLowerCase() === 'success'
  const isFailed = String(job.status).toLowerCase() === 'failed'

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', background: 'var(--bg-panel)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', alignItems: 'center' }}>
        <strong style={{ fontSize: '1.1rem' }}>{job.job_name}</strong>
        <span style={{ 
          color: isSuccess ? 'var(--green)' : isFailed ? 'var(--red)' : 'var(--blue)',
          fontWeight: 'bold',
          padding: '0.2rem 0.5rem',
          borderRadius: '4px',
          background: 'rgba(0,0,0,0.1)'
        }}>
          {String(job.status).toUpperCase()} {job.duration_seconds ? `(${job.duration_seconds}s)` : '(Running...)'}
        </span>
      </div>
      <pre style={{ 
        margin: 0, 
        padding: '1rem', 
        background: '#1e1e1e', 
        color: '#d4d4d4',
        fontSize: '0.8rem', 
        maxHeight: '200px', 
        overflowY: 'auto', 
        whiteSpace: 'pre-wrap',
        borderRadius: '4px',
        border: '1px solid #333'
      }}>
        {log || 'Waiting for logs...'}
      </pre>
    </div>
  )
}

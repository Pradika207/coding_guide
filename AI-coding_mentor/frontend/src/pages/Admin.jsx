import { Activity, AlertTriangle, ArrowUpRight, Database, Gauge, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react';
import { useResource } from '../hooks/useResource';
import { api } from '../services/api';

function MetricCard({ label, value, detail, icon: Icon }) {
  return (
    <div className="panel admin-card">
      <div className="admin-card-head">
        <span className="admin-icon"><Icon size={16} /></span>
        <span className="section-eyebrow">{label}</span>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function AdminDashboard() {
  const overview = useResource(api.adminOverview);
  const system = overview.data?.system || {};
  const model = overview.data?.model || {};
  const monitoring = overview.data?.monitoring || {};
  const retraining = overview.data?.retraining || {};
  const dvc = overview.data?.dvc || {};
  const mlflow = overview.data?.mlflow || {};

  const healthState = system?.backend?.api_status || 'unknown';
  const modelStatus = system?.ml?.status || 'unknown';
  const monitoringStatus = monitoring?.status || 'unknown';

  return (
    <div className="app-shell admin-shell">
      <main className="dashboard-main admin-main">
        <div className="dashboard-intro admin-intro">
          <div>
            <span className="intro-overline">ADMIN CONTROL CENTER</span>
            <h1>Platform health & ML operations</h1>
          </div>
          <div className="admin-badge"><ShieldCheck size={14} /> Admin access</div>
        </div>

        {overview.loading && <div className="route-loader" role="status">Loading admin overview…</div>}
        {overview.error && <div className="inline-alert" role="alert">{overview.error.message || 'Unable to load admin data.'}</div>}

        {!overview.loading && !overview.error && (
          <>
            <section className="admin-grid admin-grid-top">
              <MetricCard label="Backend" value={healthState} detail={system?.backend?.api_version || 'API version'} icon={Activity} />
              <MetricCard label="Model status" value={modelStatus} detail={model?.model?.version || 'Model version unavailable'} icon={Gauge} />
              <MetricCard label="Monitoring" value={monitoringStatus} detail={`${monitoring?.prediction_count || 0} samples`} icon={TrendingUp} />
              <MetricCard label="Retraining" value={retraining?.status || 'pending'} detail={retraining?.trigger || 'No retraining trigger yet'} icon={ArrowUpRight} />
            </section>

            <section className="admin-grid admin-grid-lower">
              <div className="panel admin-section">
                <div className="section-title-row">
                  <div><span className="section-eyebrow"><Sparkles size={13} /> MLOPS overview</span><h2>Model & dataset</h2></div>
                </div>
                <ul className="admin-list">
                  <li><span>Model name</span><strong>{model?.model?.name || 'AI-Coding-Mentor-Skill-Predictor'}</strong></li>
                  <li><span>Model version</span><strong>{model?.model?.version || 'unknown'}</strong></li>
                  <li><span>Feature version</span><strong>{model?.model?.feature_version || 'unknown'}</strong></li>
                  <li><span>Dataset version</span><strong>{overview.data?.dataset?.version || 'unknown'}</strong></li>
                  <li><span>Sample count</span><strong>{overview.data?.dataset?.sample_count || 0}</strong></li>
                </ul>
              </div>

              <div className="panel admin-section">
                <div className="section-title-row">
                  <div><span className="section-eyebrow"><Database size={13} /> Data pipeline</span><h2>ML workflow</h2></div>
                </div>
                <ul className="admin-list">
                  <li><span>DVC status</span><strong>{dvc?.status || 'unknown'}</strong></li>
                  <li><span>Pipeline stages</span><strong>{(dvc?.pipeline || []).length ? dvc.pipeline.join(', ') : 'none'}</strong></li>
                  <li><span>MLflow tracking</span><strong>{mlflow?.tracking_status || 'unavailable'}</strong></li>
                  <li><span>MLflow run</span><strong>{mlflow?.latest_run_id || 'not available'}</strong></li>
                  <li><span>Registry</span><strong>{mlflow?.registry_status || 'not available'}</strong></li>
                </ul>
              </div>

              <div className="panel admin-section wide-panel">
                <div className="section-title-row">
                  <div><span className="section-eyebrow"><AlertTriangle size={13} /> Monitoring</span><h2>Drift signals</h2></div>
                </div>
                <ul className="admin-list">
                  <li><span>Status</span><strong>{monitoringStatus}</strong></li>
                  <li><span>Prediction count</span><strong>{monitoring?.prediction_count || 0}</strong></li>
                  <li><span>Warning features</span><strong>{(monitoring?.warning_features || []).join(', ') || 'none'}</strong></li>
                  <li><span>Drifted features</span><strong>{(monitoring?.drifted_features || []).join(', ') || 'none'}</strong></li>
                  <li><span>Promotion decision</span><strong>{retraining?.promotion_decision || 'pending'}</strong></li>
                </ul>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default AdminDashboard;

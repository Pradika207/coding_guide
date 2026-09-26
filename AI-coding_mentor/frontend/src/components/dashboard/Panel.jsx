import { RefreshCw } from 'lucide-react';

export function Panel({ title, subtitle, action, className = '', children, loading = false, error = null, onRetry, empty = null }) {
  return <section className={`panel ${className}`}>
    <div className="panel-heading">
      <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      {action}
    </div>
    {loading ? <div className="panel-skeleton" aria-label={`Loading ${title}`}><i /><i /><i /></div>
      : error ? <div className="panel-state"><p>Unable to load this section. Try again.</p><button type="button" className="text-button" onClick={onRetry}><RefreshCw size={14} /> Retry</button></div>
      : empty ? <div className="panel-state empty-state">{empty}</div>
      : children}
  </section>;
}

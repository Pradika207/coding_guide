import { ArrowRight, Award, LockKeyhole, Medal, Sparkles } from 'lucide-react';
import { Panel } from './Panel';

const badgeColors = ['badge-coral', 'badge-violet', 'badge-blue', 'badge-mint'];

export default function BadgeShowcase({ resource }) {
  const badges = resource.data || [];
  const empty = <><Award size={24} /><strong>Your first badge is within reach</strong><span>Complete a learning activity to start your achievements shelf.</span><a className="text-button" href="/lessons">Explore lessons <ArrowRight size={14} /></a></>;
  return <Panel title="Achievements" subtitle="Milestones you have earned" className="badges-panel" loading={resource.loading} error={resource.error} onRetry={resource.retry} empty={!badges.length && !resource.error && !resource.loading ? empty : null}>
    <div className="badge-list">{badges.slice(0, 4).map((badge, index) => <div className="badge-item" key={badge.badge_id}>
      <span className={`badge-emblem ${badgeColors[index % badgeColors.length]}`}><Medal size={21} /></span>
      <span className="badge-copy"><strong>{badge.name}</strong><small>{badge.description}</small></span>
      <span className="earned-check"><Sparkles size={14} /></span>
    </div>)}</div>
    <div className="badge-footnote"><LockKeyhole size={13} /> More milestones unlock as you learn</div>
  </Panel>;
}

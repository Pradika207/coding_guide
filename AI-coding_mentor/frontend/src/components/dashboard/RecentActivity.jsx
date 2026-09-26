import { ArrowRight, BookOpen, CheckCircle2, Flame, Gamepad2, Trophy, Zap } from 'lucide-react';
import { Panel } from './Panel';

const eventMeta = {
  lesson_completed: { label: 'Lesson completed', icon: BookOpen, color: 'activity-violet' },
  quiz_completed: { label: 'Quiz completed', icon: CheckCircle2, color: 'activity-green' },
  coding_easy_completed: { label: 'Easy challenge solved', icon: Gamepad2, color: 'activity-blue' },
  coding_medium_completed: { label: 'Medium challenge solved', icon: Gamepad2, color: 'activity-blue' },
  coding_hard_completed: { label: 'Hard challenge solved', icon: Gamepad2, color: 'activity-orange' },
  assessment_completed: { label: 'Assessment completed', icon: Trophy, color: 'activity-gold' },
};

function relativeDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  return days <= 0 ? 'Today' : days === 1 ? 'Yesterday' : `${days} days ago`;
}

export default function RecentActivity({ xp, xpLoading, xpError, retryXp }) {
  const empty = <><Flame size={23} /><strong>Your story starts here</strong><span>Start your first lesson to build your learning history.</span><a className="text-button" href="/lessons">Browse lessons <ArrowRight size={14} /></a></>;
  return <Panel title="Recent activity" subtitle="Your latest learning wins" className="activity-panel" loading={xpLoading} error={xpError} onRetry={retryXp} empty={!xp?.length && !xpError && !xpLoading ? empty : null}>
    <div className="activity-list">{xp?.slice(0, 6).map((event) => {
      const meta = eventMeta[event.event_type] || { label: event.event_type.replaceAll('_', ' '), icon: Zap, color: 'activity-neutral' };
      const Icon = meta.icon;
      return <div className="activity-item" key={event.event_id}>
        <span className={`activity-icon ${meta.color}`}><Icon size={16} /></span>
        <span className="activity-copy"><strong>{meta.label}</strong><small>{relativeDate(event.created_at)}</small></span>
        <span className="activity-xp">+{event.xp_amount} XP</span>
      </div>;
    })}</div>
  </Panel>;
}

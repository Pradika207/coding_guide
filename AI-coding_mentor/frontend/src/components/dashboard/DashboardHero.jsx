import { ArrowRight, Flame, Sparkles, Target, Zap } from 'lucide-react';

function Stat({ icon: Icon, label, value, detail, tone }) {
  return <div className={`hero-stat ${tone}`}>
    <span className="stat-icon"><Icon size={17} /></span>
    <div><span className="stat-label">{label}</span><strong>{value}</strong><small>{detail}</small></div>
  </div>;
}

export default function DashboardHero({ user, gamification, gamLoading, gamError, retryGam }) {
  const progress = Math.min(100, Math.max(0, Number(gamification?.daily_goal_progress || 0) * 100));
  const firstName = user?.name?.trim()?.split(/\s+/)[0] || 'there';
  return <section className="hero-panel">
    <div className="hero-orb orb-one" /><div className="hero-orb orb-two" />
    <div className="hero-copy">
      <div className="eyebrow hero-eyebrow"><Sparkles size={14} /> YOUR LEARNING SPACE</div>
      <h1>Good to see you, {firstName}<span className="wave">✦</span></h1>
      <p>Small steps today. Stronger skills tomorrow.</p>
      <a className="hero-link" href="#learning">Pick up where you left off <ArrowRight size={16} /></a>
    </div>
    <div className="hero-stats" aria-label="Learning progress summary">
      {gamLoading ? <div className="hero-stat-skeleton" aria-label="Loading progress" /> : gamError ? <div className="stat-error"><span>Progress data is taking a break.</span><button onClick={retryGam}>Retry</button></div> : <>
        <Stat icon={Zap} label="TOTAL XP" value={(gamification?.total_xp ?? 0).toLocaleString()} detail={`Level ${gamification?.level ?? 1}`} tone="stat-xp" />
        <Stat icon={Flame} label="CURRENT STREAK" value={`${gamification?.current_streak ?? 0} days`} detail={`Best: ${gamification?.longest_streak ?? 0} days`} tone="stat-streak" />
        <Stat icon={Target} label="DAILY GOAL" value={`${gamification?.daily_xp ?? 0} / ${gamification?.daily_goal_xp ?? 0} XP`} detail={`${Math.round(progress)}% complete`} tone="stat-goal" />
      </>}
    </div>
    {!gamLoading && !gamError && <div className="hero-progress" aria-label={`Daily goal ${Math.round(progress)} percent complete`}><span style={{ width: `${progress}%` }} /></div>}
  </section>;
}

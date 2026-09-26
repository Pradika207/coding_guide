import { useMemo } from 'react';
import { ArrowRight, BookOpen, BrainCircuit, CheckCircle2, Code2, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../auth/AuthContext';
import { useResource } from '../hooks/useResource';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardHero from '../components/dashboard/DashboardHero';
import RoadmapProgress from '../components/dashboard/RoadmapProgress';
import SkillOverview from '../components/dashboard/SkillOverview';
import Recommendations from '../components/dashboard/Recommendations';
import RecentActivity from '../components/dashboard/RecentActivity';
import BadgeShowcase from '../components/dashboard/BadgeShowcase';

function formatTopic(value = '') { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export default function Dashboard() {
  const { user } = useAuth();
  const gam = useResource(api.gamification);
  const roadmap = useResource(api.roadmap);
  const currentTopic = useResource(api.currentRoadmapTopic);
  const lesson = useResource(api.currentLesson);
  const badges = useResource(api.badges);
  const xp = useResource(api.xpHistory);
  const recommendations = useResource(api.recommendations);
  const skill = useResource(api.skillProfile);
  const assessmentHistory = useResource(api.assessmentHistory);
  const language = useResource(api.language);

  const latestSession = assessmentHistory.data?.[0]?.session_id;
  const loadLatestResult = useMemo(() => () => latestSession ? api.assessmentResult(latestSession) : Promise.resolve(null), [latestSession]);
  const assessment = useResource(loadLatestResult, [latestSession]);
  const topic = currentTopic.data?.topic || roadmap.data?.current_topic;
  const loadTopicProgress = useMemo(() => () => topic ? api.lessonProgress(topic) : Promise.resolve(null), [topic]);
  const topicProgress = useResource(loadTopicProgress, [topic]);

  const hasAssessment = Boolean(assessmentHistory.data?.length);
  const localHour = new Date().getHours();
  const dayPart = localHour < 12 ? 'morning' : localHour < 18 ? 'afternoon' : 'evening';
  const learningLinks = [
    { icon: BookOpen, label: 'Continue a lesson', detail: lesson.data?.title || 'Follow your personalized roadmap', href: lesson.data?.lesson_id ? `/learn/lesson/${encodeURIComponent(lesson.data.lesson_id)}` : '/learn', tone: 'quick-violet' },
    { icon: Code2, label: 'Practice a problem', detail: 'Build confidence one challenge at a time', href: '#practice', tone: 'quick-blue' },
    { icon: BrainCircuit, label: 'Ask for a hint', detail: 'Get a nudge, not the whole answer', href: '#practice', tone: 'quick-amber' },
  ];

  return <div className="app-shell">
    <DashboardHeader />
    <main className="dashboard-main">
      <div className="dashboard-intro">
        <div><span className="intro-overline">YOUR PERSONAL LEARNING HUB</span><h1>Good {dayPart}, {user?.name?.trim()?.split(/\s+/)[0] || 'there'} <span aria-hidden="true">✦</span></h1><p>Keep showing up. Your next breakthrough is closer than you think.</p></div>
        <div className="language-pill"><span className="language-dot" /> Learning in <b>{formatTopic(language.data?.selected_language || user?.selected_language || 'your language')}</b></div>
      </div>

      <DashboardHero user={user} gamification={gam.data} gamLoading={gam.loading} gamError={gam.error} retryGam={gam.retry} />

      <div className="dashboard-grid dashboard-grid-primary" id="learning">
        <RoadmapProgress roadmap={roadmap.data} roadmapLoading={roadmap.loading} roadmapError={roadmap.error} retryRoadmap={roadmap.retry} currentTopic={currentTopic.data} lesson={lesson.data} lessonLoading={lesson.loading} lessonError={lesson.error} retryLesson={lesson.retry} topicProgress={topicProgress.data} progressLoading={topicProgress.loading} />
        <SkillOverview profile={skill.data} profileLoading={skill.loading} profileError={skill.error} retryProfile={skill.retry} assessment={assessment.data} assessmentLoading={assessment.loading || assessmentHistory.loading} assessmentError={assessment.error || assessmentHistory.error} retryAssessment={() => { assessmentHistory.retry(); assessment.retry(); }} />
      </div>

      <section className="quick-start" aria-labelledby="quick-start-title">
        <div className="section-title-row"><div><span className="section-eyebrow"><Sparkles size={13} /> MAKE TODAY COUNT</span><h2 id="quick-start-title">Your next best steps</h2></div><span className="soft-pill">A little progress goes a long way</span></div>
        <div className="quick-grid">{learningLinks.map(({ icon: Icon, label, detail, href, tone }) => <a className={`quick-card ${tone}`} href={href} key={label}><span className="quick-icon"><Icon size={18} /></span><span className="quick-card-copy"><strong>{label}</strong><small>{detail}</small></span><ArrowRight className="quick-arrow" size={17} /></a>)}</div>
      </section>

      <div id="practice"><Recommendations resource={recommendations} /></div>

      <div className="dashboard-grid dashboard-grid-secondary" id="progress">
        <RecentActivity xp={xp.data} xpLoading={xp.loading} xpError={xp.error} retryXp={xp.retry} />
        <BadgeShowcase resource={badges} />
      </div>

      {!hasAssessment && !assessmentHistory.loading && <div className="assessment-nudge"><span className="nudge-icon"><CheckCircle2 size={18} /></span><span><strong>Unlock your personal roadmap</strong><small>Take a short coding assessment so your learning path can meet you where you are.</small></span><a href="/assessment">Explore assessment <ArrowRight size={15} /></a></div>}
      <footer className="dashboard-footer"><span>Built for curious minds who keep going.</span><span>AI Coding Mentor <i>·</i> Learn at your pace</span></footer>
    </main>
  </div>;
}

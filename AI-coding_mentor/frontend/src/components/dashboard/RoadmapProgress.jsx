import { ArrowRight, BookOpen, Check, Circle, Compass, Play } from 'lucide-react';
import { Panel } from './Panel';

function topicLabel(value = '') { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export default function RoadmapProgress({ roadmap, roadmapLoading, roadmapError, retryRoadmap, currentTopic, lesson, lessonLoading, lessonError, retryLesson, topicProgress, progressLoading }) {
  const topics = roadmap?.topics || [];
  const current = currentTopic?.topic || roadmap?.current_topic;
  const currentIndex = topics.findIndex((item) => item.topic === current);
  const progress = topicProgress?.progress_percent ?? (topics.length ? Math.round((topics.filter((item) => item.status === 'completed').length / topics.length) * 100) : 0);
  const roadmapMissing = roadmapError?.status === 404;
  const empty = !roadmap && (!roadmapError || roadmapMissing) && <><Compass size={24} /><strong>Your roadmap is waiting</strong><span>Take your coding assessment to unlock a personalized learning path.</span><a className="button button-dark button-small" href="/assessment">Explore assessment <ArrowRight size={15} /></a></>;
  return <Panel title="Your learning path" subtitle="A clear route from here to your next milestone" className="roadmap-panel" loading={roadmapLoading} error={roadmapError && !roadmapMissing ? roadmapError : null} onRetry={retryRoadmap} empty={empty}>
    <div className="roadmap-content">
      <div className="roadmap-topline"><span className="roadmap-kicker"><Compass size={14} /> PERSONALIZED ROADMAP</span><span className="roadmap-percent">{progressLoading ? '—' : `${progress}%`} <small>complete</small></span></div>
      <div className="roadmap-track" aria-label={`${progress}% roadmap progress`}><span style={{ width: `${progress}%` }} /></div>
      <div className="topic-path">
        {topics.slice(0, 5).map((item, index) => <div className={`path-topic ${item.status} ${item.topic === current ? 'path-current' : ''}`} key={item.topic}>
          <span className="path-node">{item.status === 'completed' ? <Check size={13} /> : item.topic === current ? <span /> : <Circle size={8} />}</span>
          <span>{topicLabel(item.topic)}</span>{index < Math.min(topics.length, 5) - 1 && <i className="path-connector" />}
        </div>)}
        {!topics.length && current && <span className="current-topic-chip">{topicLabel(current)}</span>}
      </div>
      <div className="continue-card">
        <div className="continue-icon"><BookOpen size={19} /></div>
        <div className="continue-copy">
          <span className="continue-label">{lesson ? 'PICK UP WHERE YOU LEFT OFF' : current ? 'NEXT UP IN YOUR ROADMAP' : 'YOUR NEXT STEP'}</span>
          {lessonLoading ? <div className="inline-skeleton" /> : lessonError ? <strong>Lesson details unavailable</strong> : <strong>{lesson?.title || (current ? `${topicLabel(current)} lesson` : 'Take your first assessment')}</strong>}
          <span className="continue-meta">{lesson?.topic ? topicLabel(lesson.topic) : current ? topicLabel(current) : 'Personalized learning path'}</span>
        </div>
        <a className="button button-dark button-small" href={lesson?.lesson_id ? `/lessons/${encodeURIComponent(lesson.lesson_id)}` : '/assessment'} aria-label="Continue learning">{lesson?.lesson_id ? 'Continue' : 'Get started'} <Play size={13} fill="currentColor" /></a>
      </div>
      {currentIndex >= 0 && <p className="roadmap-note">Currently exploring <b>{topicLabel(current)}</b>{topics[currentIndex + 1] && <> · Next: {topicLabel(topics[currentIndex + 1].topic)}</>}</p>}
    </div>
  </Panel>;
}

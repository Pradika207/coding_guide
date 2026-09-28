import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Award, Blocks, BookOpen, Castle, Check, Flame, Heart, LockKeyhole, Mountain, Network, Play, Route, Sparkles, Star, Target, Trees, X, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useResource } from '../hooks/useResource';
import { api } from '../services/api';
import './LearningPath.css';

const PATH_X = [15, 29, 48, 70, 83, 73, 54, 34, 17, 28, 49, 70, 82, 66, 45, 25, 38, 62];
const WORLDS = [
  { start: 1, end: 5, title: 'Coding Valley', subtitle: 'WORLD 1 · CODING FOUNDATIONS', icon: Trees, className: 'foundations' },
  { start: 6, end: 11, title: 'Data Structure Forest', subtitle: 'WORLD 2 · CORE DATA STRUCTURES', icon: Blocks, className: 'structures' },
  { start: 12, end: 14, title: 'Algorithm Mountains', subtitle: 'WORLD 3 · ALGORITHMS', icon: Mountain, className: 'algorithms' },
  { start: 15, end: 18, title: 'Advanced Observatory', subtitle: 'WORLD 4 · ADVANCED CODING', icon: Network, className: 'advanced' },
];
const formatTopic = (value = '') => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
const clampPercent = (value) => Math.max(0, Math.min(100, Number(value) || 0));

function getNodeState(topic, currentTopic) {
  if (topic.status === 'completed') return 'completed';
  if (topic.status === 'locked') return 'locked';
  if (topic.status === 'recommended') return 'recommended';
  if (topic.status === 'unlocked' || topic.status === 'current' || topic.topic === currentTopic) return 'current';
  return 'locked';
}

function getProgress(topic, progress) {
  if (Number.isFinite(progress?.progress_percent)) return clampPercent(progress.progress_percent);
  return topic.status === 'completed' ? 100 : null;
}

function getStars(score) {
  if (!Number.isFinite(score)) return 0;
  if (score >= 90) return 3;
  if (score >= 80) return 2;
  if (score >= 60) return 1;
  return 0;
}

function EmptyLearningWorld({ message }) {
  return (
    <section className="learning-map-empty has-empty-world">
      <div className="empty-world-copy">
        <span className="learning-kicker"><Trees size={14} /> CODING WORLD</span>
        <h2>Your adventure starts here</h2>
        <p>{message}</p>
        <Link className="learning-action-button" to="/assessment">Take assessment <ArrowRight size={16} /></Link>
        <small>Complete the assessment to reveal your personalized levels.</small>
      </div>
      <svg className="empty-world-art" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMax meet" aria-hidden="true" focusable="false">
        <path className="empty-world-hill back" d="M0 438C134 380 204 425 326 382s208-92 330-43 228 55 344 3v358H0z" />
        <path className="empty-world-trail" d="M760 10C740 105 825 136 737 216S515 295 564 390s177 122 76 192-175 65-202 118" />
        <path className="empty-world-hill front" d="M0 544c145-60 251 13 376-2s220-99 342-42 180 48 282 15v185H0z" />
        <g className="empty-world-tree" transform="translate(120 414)"><path d="m42 0 40 71H2zM42 45l48 78H-6z" /><path d="M35 116h14v45H35z" /></g>
        <g className="empty-world-tree small" transform="translate(816 396)"><path d="m42 0 40 71H2zM42 45l48 78H-6z" /><path d="M35 116h14v45H35z" /></g>
        <g className="empty-world-code" transform="translate(673 478)"><rect width="68" height="48" rx="10" /><path d="m25 15-9 9 9 9m18-18 9 9-9 9m-5-22-7 26" /></g>
        <g className="empty-world-spark" transform="translate(279 492)"><path d="M16 0 20 12 32 16 20 20 16 32 12 20 0 16 12 12z" /></g>
      </svg>
    </section>
  );
}

export default function Learn() {
  const { user } = useAuth();
  const roadmapResource = useResource(api.getRoadmap);
  const gamificationResource = useResource(api.gamification);
  const [selectedTopicName, setSelectedTopicName] = useState(null);

  const roadmap = roadmapResource.data;
  const topics = useMemo(() => [...(roadmap?.topics || [])].sort((left, right) => left.order - right.order), [roadmap?.topics]);
  const currentTopicName = roadmap?.current_topic;
  const selectedTopic = topics.find((item) => item.topic === selectedTopicName) || null;

  useEffect(() => {
    if (selectedTopicName && !topics.some((item) => item.topic === selectedTopicName)) setSelectedTopicName(null);
  }, [selectedTopicName, topics]);

  useEffect(() => {
    if (!selectedTopic) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setSelectedTopicName(null);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [selectedTopic]);

  const progressLoader = useMemo(() => {
    if (!topics.length) return () => Promise.resolve({});
    return async () => {
      const entries = await Promise.all(topics.map(async (item) => {
        try {
          return [item.topic, await api.getTopicProgress(item.topic)];
        } catch {
          return [item.topic, null];
        }
      }));
      return Object.fromEntries(entries);
    };
  }, [topics]);
  const topicProgress = useResource(progressLoader, [roadmap?.roadmap_id]);
  const topicLessons = useResource(() => (
    selectedTopic?.topic ? api.getLessons({ topic: selectedTopic.topic }) : Promise.resolve([])
  ), [selectedTopic?.topic]);
  const lessons = topicLessons.data || [];
  const recommendedLesson = lessons[0] || null;
  const selectedProgress = selectedTopic ? topicProgress.data?.[selectedTopic.topic] : null;
  const selectedProgressPercent = selectedTopic ? getProgress(selectedTopic, selectedProgress) : null;
  const gamification = gamificationResource.data;
  const currentTopic = topics.find((item) => item.topic === currentTopicName) || null;
  const completedCount = topics.filter((item) => item.status === 'completed').length;
  const overallProgress = topics.length
    ? Math.round(topics.reduce((total, item) => total + (getProgress(item, topicProgress.data?.[item.topic]) ?? 0), 0) / topics.length)
    : 0;
  const dailyProgress = clampPercent((gamification?.daily_goal_progress || 0) * 100);
  const stepHeight = 218;
  const mapHeight = Math.max(300, topics.length * stepHeight + 90);
  const pathParts = topics.slice(0, -1).map((topic, index) => {
    const fromX = PATH_X[index % PATH_X.length] * 10;
    const toX = PATH_X[(index + 1) % PATH_X.length] * 10;
    const fromY = 76 + index * stepHeight;
    const toY = fromY + stepHeight;
    const curve = `M ${fromX} ${fromY} C ${fromX} ${fromY + 112}, ${toX} ${toY - 112}, ${toX} ${toY}`;
    const completed = topic.status === 'completed';
    return { curve, completed };
  });
  const zoneBands = WORLDS.map((world) => {
    const firstIndex = topics.findIndex((topic) => topic.order >= world.start && topic.order <= world.end);
    if (firstIndex < 0) return null;
    const nextWorldIndex = topics.findIndex((topic) => topic.order > world.end);
    const lastIndex = nextWorldIndex < 0 ? topics.length : nextWorldIndex;
    const top = Math.max(0, 76 + firstIndex * stepHeight - 124);
    const bottom = nextWorldIndex < 0 ? mapHeight : 76 + lastIndex * stepHeight - 96;
    return { ...world, top, height: Math.max(220, bottom - top) };
  }).filter(Boolean);

  return (
    <div className="learning-game-shell">
      <header className="learning-game-nav">
        <Link className="learning-game-brand" to="/dashboard" aria-label="AI Coding Mentor dashboard">
          <span className="learning-brand-icon"><Sparkles size={18} /></span>
          <span>code<span>mentor</span></span>
        </Link>
        <nav aria-label="Learning navigation">
          <Link to="/dashboard">Dashboard</Link>
          <Link className="active" to="/learn" aria-current="page">Learning path</Link>
          <Link to="/dashboard#practice">Practice</Link>
        </nav>
        <span className="learning-nav-streak"><Flame size={16} /> {gamification?.current_streak ?? '—'} day streak</span>
      </header>

      <main className="learning-game-main">
        <section className="learning-game-intro">
          <div>
            <span className="learning-kicker"><Route size={14} /> YOUR PERSONALIZED ROUTE</span>
            <h1>Learning Path</h1>
            <p>Hey {user?.name?.split(' ')[0] || 'learner'}, every level is a real step in your coding journey.</p>
          </div>
          <div className="learning-language-mark"><span>LEARNING</span><strong>{roadmap?.language || '—'}</strong></div>
        </section>

        <section className="learning-stats" aria-label="Learning progress">
          <div className="learning-stat hearts-stat">
            <span><Heart size={15} /> HEARTS</span>
            <strong>{gamification?.hearts ?? '—'}</strong>
            <small>{gamification?.hearts == null ? 'not tracked' : 'lives remaining'}</small>
          </div>
          <div className="learning-stat current-level-stat">
            <span><Target size={15} /> CURRENT LEVEL</span>
            <strong>{gamification?.level != null ? `Level ${gamification.level}` : '—'}</strong>
            <small>{currentTopic ? formatTopic(currentTopic.topic) : 'No active level'}</small>
          </div>
          <div className="learning-stat xp-stat">
            <span><Zap size={15} /> TOTAL XP</span>
            <strong>{gamification?.total_xp?.toLocaleString() ?? '—'}</strong>
            <small>experience points</small>
          </div>
          <div className="learning-stat streak-stat">
            <span><Flame size={15} /> STREAK</span>
            <strong>{gamification?.current_streak ?? '—'} days</strong>
            <small>best: {gamification?.longest_streak ?? '—'} days</small>
          </div>
          <div className="learning-stat goal-stat">
            <div className="goal-stat-heading"><span><Star size={15} /> DAILY GOAL</span><strong>{gamification ? `${gamification.daily_xp} / ${gamification.daily_goal_xp} XP` : '—'}</strong></div>
            <div className="learning-goal-track" role="progressbar" aria-label="Daily XP goal" aria-valuenow={dailyProgress} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${dailyProgress}%` }} /></div>
            <small>{gamification ? `${dailyProgress}% complete` : 'Loading goal'}</small>
          </div>
        </section>

        <section className="roadmap-progress-band" aria-label="Overall roadmap progress">
          <div className="roadmap-progress-copy"><span>ROADMAP PROGRESS</span><strong>{roadmapResource.loading || topicProgress.loading ? '—' : `${overallProgress}%`}</strong></div>
          <div className="roadmap-progress-track" role="progressbar" aria-label="Roadmap completion" aria-valuenow={overallProgress} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${overallProgress}%` }} /></div>
          <span className="roadmap-progress-count">{completedCount} of {topics.length} levels complete</span>
        </section>

        {roadmapResource.loading ? (
          <div className="learning-map-loading" role="status">Loading your real learning path…</div>
        ) : roadmapResource.error ? (
          <EmptyLearningWorld message="Complete your coding assessment to create a personalized learning path." />
        ) : !topics.length ? (
          <EmptyLearningWorld message="Your roadmap has no levels yet. Complete an assessment to build your personalized path." />
        ) : (
          <section className="learning-map-section" aria-label="Learning levels">
            <div className="learning-map-heading">
              <div><span className="learning-kicker"><BookOpen size={14} /> {topics.length} REAL LEVELS</span><h2>Your coding trail</h2></div>
              <span className="map-language-tag">{roadmap.language}</span>
            </div>
            <div className="learning-map" style={{ height: `${mapHeight}px` }}>
              {zoneBands.map((zone) => {
                const ZoneIcon = zone.icon;
                return <div className={`world-zone zone-${zone.className}`} key={zone.className} style={{ top: `${zone.top}px`, height: `${zone.height}px` }} aria-label={zone.subtitle}>
                  <div className="zone-landscape" aria-hidden="true"><i /><i /><i /><b /><b /><b /></div>
                  <div className="world-sign"><span className="world-sign-icon"><ZoneIcon size={20} /></span><span><small>{zone.subtitle}</small><strong>{zone.title}</strong></span></div>
                </div>;
              })}
              <div className="world-decoration decor-one" aria-hidden="true"><i /><i /><span>01</span></div>
              <div className="world-decoration decor-two" aria-hidden="true"><i /><i /><span>{'{ }'}</span></div>
              <div className="world-decoration decor-three" aria-hidden="true"><i /><i /><span>⌁</span></div>
              <div className="world-decoration decor-four" aria-hidden="true"><i /><i /><span>∞</span></div>
              <svg className="learning-map-path" viewBox={`0 0 1000 ${mapHeight}`} preserveAspectRatio="none" aria-hidden="true">
                {pathParts.map((segment, index) => <g key={index} className={segment.completed ? 'path-completed' : 'path-future'}>
                  <path className="map-path-shadow" d={segment.curve} />
                  <path className="map-path-dashes" d={segment.curve} />
                </g>)}
              </svg>
              {topics.map((topic, index) => {
                const state = getNodeState(topic, currentTopicName);
                const progress = getProgress(topic, topicProgress.data?.[topic.topic]);
                const stars = getStars(topic.score);
                const isActive = topic.topic === currentTopicName;
                const isMilestone = (topic.order || index + 1) % 5 === 0 || index === topics.length - 1;
                const isFinalLevel = index === topics.length - 1;
                const stateLabel = state === 'recommended' ? 'AI recommended' : state === 'current' ? (isActive ? 'Current level' : 'Unlocked') : state === 'completed' ? 'Completed' : 'Locked';
                return (
                  <div className={`learning-map-node state-${state} side-${PATH_X[index % PATH_X.length] < 50 ? 'right' : 'left'} ${isActive ? 'is-active' : ''} ${isFinalLevel ? 'is-final-level' : ''}`} key={topic.topic} style={{ left: `${PATH_X[index % PATH_X.length]}%`, top: `${76 + index * stepHeight}px`, animationDelay: `${Math.min(index * 35, 500)}ms` }}>
                    {state === 'recommended' && <span className="node-ai-ribbon"><Sparkles size={11} /> AI RECOMMENDED</span>}
                    <button type="button" className="level-orb" onClick={() => state !== 'locked' && setSelectedTopicName(topic.topic)} disabled={state === 'locked'} aria-label={`Level ${topic.order}, ${formatTopic(topic.topic)}, ${stateLabel}${progress != null ? `, ${progress}% progress` : ''}`}>
                      {state === 'completed' ? <Check size={27} strokeWidth={3} /> : state === 'locked' ? <LockKeyhole size={24} /> : state === 'recommended' ? <Star size={27} fill="currentColor" /> : isFinalLevel ? <Castle size={27} /> : isMilestone ? <Award size={27} /> : <span>{topic.order}</span>}
                      <small className="level-orb-number">{String(topic.order).padStart(2, '0')}</small>
                    </button>
                    <div className="level-caption">
                      <span className="level-number">LEVEL {String(topic.order ?? index + 1).padStart(2, '0')}{isMilestone && <span className="milestone-flag">{isFinalLevel ? 'FINAL CHALLENGE' : 'CHECKPOINT'}</span>}</span>
                      <strong>{formatTopic(topic.topic)}</strong>
                      <span className={`level-state-text text-${state}`}>{stateLabel}</span>
                      {progress != null && <span className="level-progress-text">{progress}% lesson progress</span>}
                      {topic.score != null && <span className="level-xp-hint">ASSESSMENT SCORE</span>}
                      {topic.score != null && <span className="level-stars" aria-label={`${stars} stars from score ${topic.score}`}>
                        {[1, 2, 3].map((star) => <Star key={star} size={12} fill={star <= stars ? 'currentColor' : 'none'} />)}
                        <small>{topic.score}%</small>
                      </span>}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="map-legend" aria-label="Level status legend">
              <span><i className="legend-dot completed" /> Completed</span><span><i className="legend-dot recommended" /> Recommended</span><span><i className="legend-dot current" /> Unlocked</span><span><i className="legend-dot locked" /> Locked</span>
            </div>
          </section>
        )}
      </main>

      {selectedTopic && (
        <div className="lesson-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedTopicName(null); }}>
          <section className="lesson-modal" role="dialog" aria-modal="true" aria-labelledby="lesson-modal-title">
            <button className="lesson-modal-close" type="button" aria-label="Close level details" onClick={() => setSelectedTopicName(null)}><X size={19} /></button>
            <span className="learning-kicker"><Sparkles size={14} /> LEVEL {String(selectedTopic.order).padStart(2, '0')} · {selectedTopic.status === 'recommended' ? 'AI RECOMMENDED' : formatTopic(selectedTopic.status)}</span>
            <h2 id="lesson-modal-title">{formatTopic(selectedTopic.topic)}</h2>
            <p className="lesson-modal-lead">{selectedTopic.status === 'completed' ? 'A level you have already cleared. Revisit the lesson to sharpen your skills.' : selectedTopic.topic === currentTopicName ? 'Your recommended next step on this path.' : 'This level is open and ready when you are.'}</p>
            <div className="lesson-modal-progress">
              <div><span>Topic progress</span><strong>{selectedProgressPercent == null ? (topicProgress.loading ? 'Loading' : 'Not started') : `${selectedProgressPercent}%`}</strong></div>
              <div className="lesson-modal-track"><span style={{ width: `${selectedProgressPercent ?? 0}%` }} /></div>
              <small>{selectedProgress?.completed_lessons != null && selectedProgress?.total_lessons != null ? `${selectedProgress.completed_lessons} of ${selectedProgress.total_lessons} lessons complete` : selectedTopic.score != null ? `Assessment score: ${selectedTopic.score}%` : 'Progress updates as you complete lessons.'}</small>
            </div>
            <div className="recommended-action"><span>RECOMMENDED ACTION</span><strong>{topicLessons.loading ? 'Finding a lesson…' : recommendedLesson ? `${recommendedLesson.status === 'in_progress' ? 'Continue' : 'Start'} ${recommendedLesson.title}` : 'No lesson is currently available for this topic.'}</strong></div>
            <Link className={`learning-action-button modal-start-button ${!recommendedLesson ? 'is-disabled' : ''}`} to={recommendedLesson ? `/learn/lesson/${encodeURIComponent(recommendedLesson.lesson_id)}` : '#'} aria-disabled={!recommendedLesson} onClick={(event) => { if (!recommendedLesson) event.preventDefault(); }}>
              START LEARNING <ArrowRight size={17} />
            </Link>
          </section>
        </div>
      )}
    </div>
  );
}

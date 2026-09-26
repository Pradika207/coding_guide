import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BookOpen, BrainCircuit, Check, Lock, Route, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../auth/AuthContext';
import { useResource } from '../hooks/useResource';

const formatTopic = (value = '') => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

function statusTone(status) {
  if (status === 'completed') return 'completed';
  if (status === 'recommended' || status === 'current') return 'current';
  if (status === 'unlocked') return 'unlocked';
  return 'locked';
}

export default function Learn() {
  const { user } = useAuth();
  const roadmapResource = useResource(api.getRoadmap);
  const currentLessonResource = useResource(api.getCurrentLesson);
  const gamificationResource = useResource(api.gamification);
  const [selectedTopicName, setSelectedTopicName] = useState(null);

  const roadmap = roadmapResource.data;
  const topics = roadmap?.topics || [];
  const currentTopic = roadmap?.current_topic || topics.find((item) => item.status === 'recommended')?.topic || topics[0]?.topic || '';

  useEffect(() => {
    if (!topics.length) setSelectedTopicName(null);
    else if (!selectedTopicName || !topics.some((item) => item.topic === selectedTopicName)) {
      setSelectedTopicName(currentTopic);
    }
  }, [currentTopic, selectedTopicName, topics]);

  const selectedTopic = topics.find((item) => item.topic === selectedTopicName) || topics.find((item) => item.topic === currentTopic) || topics[0] || null;

  const progressLoader = useMemo(() => {
    if (!topics.length) return () => Promise.resolve({});
    return async () => {
      const entries = await Promise.all(topics.map(async (item) => {
        try {
          const progress = await api.getTopicProgress(item.topic);
          return [item.topic, progress?.progress_percent ?? (item.status === 'completed' ? 100 : 0)];
        } catch {
          return [item.topic, item.status === 'completed' ? 100 : 0];
        }
      }));
      return Object.fromEntries(entries);
    };
  }, [topics]);

  const topicProgress = useResource(progressLoader, [roadmap?.roadmap_id]);

  const topicLessons = useResource(() => {
    if (!selectedTopic?.topic) return Promise.resolve([]);
    return api.getLessons({ topic: selectedTopic.topic });
  }, [selectedTopic?.topic]);

  return (
    <div className="app-shell learning-shell">
      <header className="topbar">
        <a className="brand" href="/dashboard" aria-label="AI Coding Mentor dashboard">
          <span className="brand-mark"><Sparkles size={19} /></span>
          <span className="brand-copy">code<span>mentor</span></span>
        </a>
        <nav className="main-nav" aria-label="Learning navigation">
          <a className="nav-link" href="/dashboard">Dashboard</a>
          <a className="nav-link active" href="/learn">Learn</a>
          <a className="nav-link" href="/dashboard#practice">Practice</a>
          <a className="nav-link" href="/dashboard#progress">Progress</a>
        </nav>
      </header>

      <main className="learn-page">
        <section className="learn-hero panel">
          <div>
            <span className="section-eyebrow"><Route size={12} /> YOUR CODING JOURNEY</span>
            <h1>Your coding journey</h1>
            <p>Welcome back, {user?.name?.split(' ')[0] || 'Student'}. Build steady momentum, one concept at a time.</p>
          </div>
          <div className="learn-meta-grid">
            <div className="meta-pill"><strong>{roadmap?.language || 'Python'}</strong><span>Language</span></div>
            <div className="meta-pill"><strong>{roadmap?.topics?.filter((item) => item.status === 'completed').length || 0}</strong><span>Completed</span></div>
            <div className="meta-pill"><strong>{gamificationResource.data?.current_streak || 0} days</strong><span>Streak</span></div>
            <div className="meta-pill"><strong>{gamificationResource.data?.total_xp || 0} XP</strong><span>XP</span></div>
          </div>
        </section>

        <div className="learn-layout">
          <section className="panel learn-main-panel">
            <div className="section-title-row">
              <div>
                <span className="section-eyebrow"><BookOpen size={12} /> LEARNING PATH</span>
                <h2>Journey overview</h2>
              </div>
            </div>

            {roadmapResource.loading ? (
              <div className="panel-skeleton" aria-label="Loading learning roadmap"><i /><i /><i /></div>
            ) : roadmapResource.error ? (
              <div className="panel-state">
                <p>Complete your coding assessment to generate your personalized learning path.</p>
                <Link className="button button-dark button-small" to="/dashboard">Take Assessment</Link>
              </div>
            ) : !topics.length ? (
              <div className="panel-state empty-state">
                <BrainCircuit size={22} />
                <strong>Your personalized roadmap is not ready yet.</strong>
                <span>Complete your coding assessment to generate your personalized learning path.</span>
                <Link className="button button-dark button-small" to="/dashboard">Take Assessment</Link>
              </div>
            ) : (
              <div className="learning-path" aria-label="Learning roadmap">
                {topics.map((topic, index) => {
                  const status = topic.status || 'locked';
                  const isCurrent = topic.topic === currentTopic;
                  const isLocked = status === 'locked';
                  const progressValue = topicProgress.data?.[topic.topic] ?? (status === 'completed' ? 100 : 0);
                  return (
                    <div className="learning-path-item" key={topic.topic}>
                      <button
                        type="button"
                        className={`learning-node ${statusTone(status)} ${isCurrent ? 'current' : ''}`}
                        onClick={() => !isLocked && setSelectedTopicName(topic.topic)}
                        disabled={isLocked}
                      >
                        <span className="node-status">
                          {status === 'completed' && <Check size={14} />}
                          {status === 'locked' && <Lock size={12} />}
                          {status !== 'completed' && status !== 'locked' && <span className="node-dot" />}
                        </span>
                        <span className="node-copy">
                          <strong>{formatTopic(topic.topic)}</strong>
                          <small>{status === 'completed' ? `${progressValue}% complete` : isLocked ? 'Locked' : isCurrent ? 'Continue' : 'Unlocked'}</small>
                        </span>
                      </button>
                      {index < topics.length - 1 && <span className="learning-connector" />}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <aside className="panel learn-sidebar">
            {selectedTopic ? (
              <>
                <div className="section-title-row">
                  <div>
                    <span className="section-eyebrow"><Sparkles size={12} /> TOPIC DETAIL</span>
                    <h2>Current focus</h2>
                  </div>
                </div>
                <div className="topic-detail-card">
                  <div className="topic-progress-row">
                    <span>Progress</span>
                    <strong>{topicProgress.data?.[selectedTopic.topic] ?? (selectedTopic.status === 'completed' ? 100 : 0)}%</strong>
                  </div>
                  <div className="topic-progress-bar"><i style={{ width: `${Math.max(0, Math.min(100, topicProgress.data?.[selectedTopic.topic] ?? (selectedTopic.status === 'completed' ? 100 : 0)))}%` }} /></div>
                  <div className="topic-lessons">
                    {topicLessons.loading ? <div className="panel-skeleton" aria-label="Loading topic lessons"><i /><i /><i /></div> : (topicLessons.data || []).slice(0, 4).map((lesson) => (
                      <Link key={lesson.lesson_id} className="lesson-mini" to={`/learn/lesson/${encodeURIComponent(lesson.lesson_id)}`}>
                        <span>{lesson.title}</span>
                        <ArrowRight size={14} />
                      </Link>
                    ))}
                  </div>
                  <Link className="button button-dark button-small" to={currentLessonResource.data?.lesson_id ? `/learn/lesson/${encodeURIComponent(currentLessonResource.data.lesson_id)}` : '/learn'}>
                    {selectedTopic.status === 'locked' ? 'Locked' : 'Open lesson'}
                  </Link>
                </div>
              </>
            ) : (
              <div className="panel-state empty-state">
                <BookOpen size={20} />
                <strong>No learning path available.</strong>
                <span>Complete your coding assessment to generate a personalized roadmap.</span>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, BookOpen, Code2, Sparkles } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../services/api';

const contentStyles = {
  concept: 'lesson-content-concept',
  example: 'lesson-content-example',
  tip: 'lesson-content-tip',
  warning: 'lesson-content-warning',
  summary: 'lesson-content-summary',
};

function formatLabel(value = '') {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function Lesson() {
  const { lessonId } = useParams();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [quiz, setQuiz] = useState(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    async function loadLesson() {
      setLoading(true);
      setError(null);
      try {
        const lessonData = await api.getLesson(lessonId);
        if (active) setLesson(lessonData);
      } catch (failure) {
        if (!active) return;
        if (failure instanceof ApiError && failure.status === 403) {
          setError('This lesson is locked. Complete the previous learning step to unlock it.');
        } else if (failure instanceof ApiError && failure.status === 404) {
          setError('Lesson not found.');
        } else if (failure instanceof ApiError && failure.status === 401) {
          navigate('/login');
          return;
        } else {
          setError(failure instanceof ApiError ? failure.message : 'Lesson not found.');
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    loadLesson();
    return () => { active = false; };
  }, [lessonId, navigate]);

  useEffect(() => {
    if (!lesson) return;
    let active = true;
    async function loadQuiz() {
      setQuizLoading(true);
      try {
        const quizData = await api.getLessonQuiz(lesson.lesson_id);
        if (active) setQuiz(quizData);
      } catch {
        if (active) setQuiz(null);
      } finally {
        if (active) setQuizLoading(false);
      }
    }
    loadQuiz();
    return () => { active = false; };
  }, [lesson]);

  async function handleStartLesson() {
    if (!lesson || starting) return;
    setStarting(true);
    try {
      await api.startLesson(lesson.lesson_id);
      setNotice('Lesson started.');
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        navigate('/login');
        return;
      }
      setNotice(failure instanceof ApiError ? failure.message : 'Unable to start lesson.');
    } finally {
      setStarting(false);
    }
  }

  async function handleCompleteLesson() {
    if (!lesson || completing) return;
    setCompleting(true);
    try {
      const progress = await api.completeLesson(lesson.lesson_id);
      setNotice(progress?.status === 'completed' ? 'Lesson completed successfully.' : 'Lesson updated.');
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        navigate('/login');
        return;
      }
      setNotice(failure instanceof ApiError ? failure.message : 'Unable to complete lesson.');
    } finally {
      setCompleting(false);
    }
  }

  async function handleQuizSubmit() {
    if (!quiz || !selectedAnswer) return;
    try {
      const data = await api.completeQuiz(lesson.lesson_id, quiz.quiz_id, selectedAnswer);
      setResult(data);
      setNotice('');
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        navigate('/login');
        return;
      }
      setNotice(failure instanceof ApiError ? failure.message : 'Unable to submit quiz.');
    }
  }

  if (loading) {
    return <div className="app-shell"><main className="lesson-page"><div className="panel"><div className="panel-skeleton" aria-label="Loading lesson"><i /><i /><i /></div></div></main></div>;
  }

  if (error) {
    return <div className="app-shell"><main className="lesson-page"><div className="panel panel-state"><BookOpen size={20} /><strong>{error}</strong><span>{error === 'Lesson not found.' ? 'The requested lesson could not be found.' : 'Try again or return to the learning path.'}</span><Link className="button button-dark button-small" to="/learn">Back to learning</Link></div></main></div>;
  }

  if (!lesson) return null;

  return (
    <div className="app-shell learning-shell">
      <header className="topbar">
        <Link className="brand" to="/learn" aria-label="Return to learning path">
          <span className="brand-mark"><Code2 size={19} /></span>
          <span className="brand-copy">code<span>mentor</span></span>
        </Link>
      </header>

      <main className="lesson-page">
        <div className="panel lesson-header-panel">
          <div>
            <div className="section-eyebrow"><BookOpen size={12} /> {formatLabel(lesson.topic)}</div>
            <h1>{lesson.title}</h1>
            <p>{lesson.description}</p>
          </div>
          <div className="lesson-actions">
            <button type="button" className="button button-light" onClick={handleStartLesson} disabled={starting}>{starting ? 'Starting...' : 'Start lesson'}</button>
            <button type="button" className="button button-dark" onClick={handleCompleteLesson} disabled={completing}>{completing ? 'Completing...' : 'Complete Lesson'}</button>
          </div>
        </div>

        {notice && <div className="inline-alert" role="status">{notice}</div>}

        <div className="lesson-layout">
          <section className="panel lesson-content-panel">
            <div className="lesson-content-list">
              {lesson.content?.map((item, index) => (
                <article key={`${item.title}-${index}`} className={`lesson-copy-card ${contentStyles[item.type] || ''}`}>
                  <span className="section-eyebrow content-tag">{formatLabel(item.type)}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <aside className="panel lesson-sidebar-panel">
            <div className="section-title-row">
              <div>
                <span className="section-eyebrow"><Sparkles size={12} /> QUIZ</span>
                <h2>Check your understanding</h2>
              </div>
            </div>

            {quizLoading ? <div className="panel-skeleton" aria-label="Loading quiz"><i /><i /><i /></div> : quiz ? (
              <div className="quiz-card">
                <p className="quiz-question">{quiz.question}</p>
                <div className="quiz-options">
                  {quiz.options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      className={`quiz-option ${selectedAnswer === option ? 'selected' : ''}`}
                      onClick={() => setSelectedAnswer(option)}
                    >
                      {option}
                    </button>
                  ))}
                </div>
                {!result ? (
                  <button type="button" className="button button-dark button-full" onClick={handleQuizSubmit} disabled={!selectedAnswer}>Submit answer</button>
                ) : (
                  <div className="quiz-result">
                    <strong>{result.score > 0 ? 'Correct!' : 'Not quite this time'}</strong>
                    <p>{result.score > 0 ? 'Nice work. Your answer was accepted by the backend.' : 'Review the concept and try again.'}</p>
                    <span className="xp-badge">+{result.xp_awarded || 0} XP</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="panel-state empty-state">
                <AlertTriangle size={20} />
                <strong>Quiz not available yet.</strong>
                <span>Complete the concept work and a quiz will appear here.</span>
              </div>
            )}

            <div className="lesson-nav">
              <button type="button" className="button button-light" onClick={() => navigate('/learn')}><ArrowLeft size={15} /> Previous</button>
              <button type="button" className="button button-dark" onClick={handleCompleteLesson}><ArrowRight size={15} /> Next</button>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

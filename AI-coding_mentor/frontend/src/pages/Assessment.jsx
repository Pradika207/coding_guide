import { AlertCircle, ArrowRight, BrainCircuit, CheckCircle2, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../auth/AuthContext';

const languageOptions = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
  { value: 'c', label: 'C' },
];

export default function Assessment() {
  const { user, updateLanguage } = useAuth();
  const [language, setLanguage] = useState(user?.selected_language || 'python');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [assessment, setAssessment] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [sourceCode, setSourceCode] = useState('');
  const [submission, setSubmission] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [completion, setCompletion] = useState(null);
  const [completing, setCompleting] = useState(false);
  const [roadmapReady, setRoadmapReady] = useState(false);
  const [roadmapError, setRoadmapError] = useState('');

  const startAssessment = async () => {
    setStarting(true);
    setError('');
    try {
      const preferred = language || user?.selected_language || 'python';
      await updateLanguage(preferred);
      const response = await api.startAssessment();
      if (response?.session_id && response.questions?.length === 5) {
        setAssessment(response);
        setQuestionIndex(0);
        setSourceCode('');
        setSubmission(null);
        setError('');
        return;
      }
      throw new Error('The assessment needs five questions before it can begin. Please try again.');
    } catch (caught) {
      setError(caught?.message || 'We could not begin the assessment right now.');
    } finally {
      setStarting(false);
    }
  };

  const submitAnswer = async () => {
    const question = assessment?.questions?.[questionIndex];
    if (!question || !sourceCode.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      const result = await api.submitAssessmentCode(assessment.session_id, {
        question_id: question.question_id,
        source_code: sourceCode,
        stdin: '',
      });
      setSubmission(result);
    } catch (caught) {
      setError(caught?.message || 'Your answer could not be submitted.');
    } finally {
      setSubmitting(false);
    }
  };

  const finishAssessment = async () => {
    setCompleting(true);
    setError('');
    setRoadmapError('');
    try {
      const result = await api.completeAssessment(assessment.session_id);
      setCompletion(result);
      try {
        await api.assessmentResult(assessment.session_id);
        await api.generateRoadmap();
        setRoadmapReady(true);
      } catch (caught) {
        setRoadmapError(caught?.message || 'Your assessment is complete, but the learning path could not be generated yet.');
      }
    } catch (caught) {
      setError(caught?.message || 'The assessment could not be completed.');
    } finally {
      setCompleting(false);
    }
  };

  const nextQuestion = () => {
    setQuestionIndex((current) => current + 1);
    setSourceCode('');
    setSubmission(null);
    setError('');
  };

  const activeQuestion = assessment?.questions?.[questionIndex];

  if (completion) {
    return <div className="app-shell"><main className="assessment-page"><section className="panel assessment-panel">
      <div className="assessment-header"><span className="section-eyebrow"><CheckCircle2 size={12} /> ASSESSMENT COMPLETE</span><h1>Your results are ready</h1>
        <p>You solved {completion.solved_questions} of {completion.total_questions} questions.</p></div>
      <div className="assessment-cta-row"><strong>Score: {completion.score}%</strong>{roadmapReady ? <Link className="primary-button" to="/learn">View your learning path <ArrowRight size={15} /></Link> : <Link className="secondary-button" to="/dashboard">Back to dashboard</Link>}</div>
      {roadmapError && <div className="inline-error" role="alert">{roadmapError} <Link to="/learn">Open Learning Path</Link></div>}
    </section></main></div>;
  }

  return <div className="app-shell">
    <main className="assessment-page">
      <section className="panel assessment-panel">
        {assessment ? <>
          <div className="assessment-header">
            <span className="section-eyebrow"><BrainCircuit size={12} /> ASSESSMENT IN PROGRESS</span>
            <h1>{activeQuestion ? activeQuestion.title : 'No questions available'}</h1>
            <p>{activeQuestion ? `Question ${questionIndex + 1} of ${assessment.questions.length} · ${assessment.language}` : 'There are no questions available for this assessment.'}</p>
          </div>
          {activeQuestion && <div className="assessment-layout">
            <div className="assessment-card">
              <h2>{activeQuestion.topic} · {activeQuestion.difficulty}</h2>
              <p>{activeQuestion.description}</p>
              <h3>Sample input</h3><pre>{activeQuestion.sample_input || 'No sample input'}</pre>
              <h3>Sample output</h3><pre>{activeQuestion.sample_output || 'No sample output'}</pre>
              {activeQuestion.constraints?.length > 0 && <><h3>Constraints</h3><ul>{activeQuestion.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul></>}
            </div>
            <div className="assessment-card">
              <label className="assessment-field"><span>Your solution</span>
                <textarea aria-label="Your solution" value={sourceCode} onChange={(event) => setSourceCode(event.target.value)} spellCheck={false} rows={14} />
              </label>
              {submission && <div className="inline-status" role="status">{submission.status.replaceAll('_', ' ')}{submission.stdout ? `: ${submission.stdout}` : ''}</div>}
              <div className="assessment-cta-row">
                <button className="primary-button" type="button" onClick={submitAnswer} disabled={submitting || !sourceCode.trim() || submission?.status === 'accepted'}>{submitting ? 'Submitting…' : 'Submit answer'} <ArrowRight size={15} /></button>
                {submission?.status === 'accepted' && questionIndex < assessment.questions.length - 1 && <button className="secondary-button" type="button" onClick={nextQuestion}>Next question</button>}
                {submission?.status === 'accepted' && questionIndex === assessment.questions.length - 1 && <button className="secondary-button" type="button" onClick={finishAssessment} disabled={completing}>{completing ? 'Finishing…' : 'Finish assessment'}</button>}
              </div>
            </div>
          </div>}
        </> : <>
        <div className="assessment-header">
          <span className="section-eyebrow"><Sparkles size={12} /> ASSESSMENT</span>
          <h1>Start your assessment</h1>
          <p>Measure your current coding confidence and unlock a roadmap that fits your next milestones.</p>
        </div>

        <div className="assessment-layout">
          <div className="assessment-card">
            <div className="assessment-icon"><BrainCircuit size={24} /></div>
            <h2>What to expect</h2>
            <ul>
              <li><CheckCircle2 size={15} /> 5 coding questions across core topics.</li>
              <li><CheckCircle2 size={15} /> A language-specific challenge based on your profile.</li>
              <li><CheckCircle2 size={15} /> Personalized roadmap and recommendations after completion.</li>
            </ul>
          </div>

          <div className="assessment-card">
            <label className="assessment-field">
              <span>Choose a language</span>
              <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                {languageOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>

            <div className="assessment-cta-row">
              <button className="primary-button" type="button" onClick={startAssessment} disabled={starting}>
                {starting ? 'Starting…' : 'Begin assessment'}
                <ArrowRight size={15} />
              </button>
            </div>

          </div>
        </div>
        </>}
        {error && <div className="inline-error" role="alert"><AlertCircle size={15} /> <span>{error}{error === 'Code execution service is not configured' && <small> Your answer was not evaluated. Ask an administrator to configure a secure Judge0 runner.</small>}</span></div>}
      </section>
    </main>
  </div>;
}

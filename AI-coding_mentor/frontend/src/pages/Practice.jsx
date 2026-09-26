import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, ArrowRight, BrainCircuit, Code2, Play, Sparkles, Terminal } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { useResource } from '../hooks/useResource';

const templateCode = {
  python: 'def solve():\n    # write your solution here\n    pass\n\nif __name__ == "__main__":\n    solve()\n',
  javascript: 'function solve() {\n  // write your solution here\n}\n\nsolve();\n',
  java: 'class Main {\n  public static void main(String[] args) {\n    // write your solution here\n  }\n}\n',
  cpp: '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    // write your solution here\n    return 0;\n}\n',
  c: '#include <stdio.h>\n\nint main() {\n    // write your solution here\n    return 0;\n}\n',
};

const displayLanguage = (value = '') => value.toString().replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
const titleCase = (value = '') => value.toString().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function Practice() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { questionId } = useParams();
  const preferredLanguage = user?.selected_language || 'python';
  const questionsResource = useResource(() => api.getQuestions({ language: preferredLanguage }));
  const questions = questionsResource.data?.questions ?? [];
  const fallbackQuestionId = questions[0]?.question_id ?? null;
  const selectedQuestionId = questionId || fallbackQuestionId;
  const selectedQuestion = questions.find((question) => question.question_id === selectedQuestionId) || questions[0] || null;

  const [sourceCode, setSourceCode] = useState('');
  const [stdin, setStdin] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [hint, setHint] = useState(null);
  const [hintLevel, setHintLevel] = useState(1);
  const [hintLoading, setHintLoading] = useState(false);

  useEffect(() => {
    if (!questions.length) return;
    if (!questionId && fallbackQuestionId) {
      navigate(`/practice/${encodeURIComponent(fallbackQuestionId)}`, { replace: true });
    }
  }, [fallbackQuestionId, navigate, questionId, questions.length]);

  useEffect(() => {
    if (!selectedQuestion) return;
    const starter = templateCode[selectedQuestion.language] || '// write your solution';
    setSourceCode((previous) => {
      if (!previous || previous === starter) return starter;
      return previous;
    });
    setStdin(selectedQuestion.sample_input || '');
    setResult(null);
    setHint(null);
    setHintLevel(1);
  }, [selectedQuestion]);

  const statusTone = useMemo(() => {
    const value = result?.status || 'pending';
    if (['accepted', 'success'].includes(value)) return 'success';
    if (['wrong_answer', 'runtime_error', 'compilation_error', 'time_limit_exceeded', 'memory_limit_exceeded', 'internal_error'].includes(value)) return 'danger';
    return 'neutral';
  }, [result]);

  const handleSelectQuestion = (event) => {
    const nextId = event.target.value;
    if (!nextId) return;
    navigate(`/practice/${encodeURIComponent(nextId)}`);
  };

  const runCode = async () => {
    if (!selectedQuestion) return;
    setRunning(true);
    setResult(null);
    try {
      const payload = {
        language: selectedQuestion.language,
        source_code: sourceCode,
        stdin,
      };
      const response = await api.executeCode(payload);
      setResult(response);
    } catch (error) {
      setResult({
        status: 'internal_error',
        stdout: '',
        stderr: error?.message || 'Could not run this code.',
        compile_output: '',
        execution_time: null,
        memory: null,
      });
    } finally {
      setRunning(false);
    }
  };

  const requestHint = async (nextHint = false) => {
    if (!selectedQuestion) return;
    setHintLoading(true);
    try {
      const payload = {
        question_id: selectedQuestion.question_id,
        language: selectedQuestion.language,
        code: sourceCode,
        submission_status: result?.status || 'pending',
        compiler_error: result?.compile_output || null,
        runtime_error: result?.stderr || null,
        topic: selectedQuestion.topic,
        difficulty: selectedQuestion.difficulty,
        hint_level: nextHint ? hintLevel + 1 : hintLevel,
      };

      const response = nextHint ? await api.getNextTutorHint(payload) : await api.getTutorHint(payload);
      setHint(response);
      setHintLevel(response?.hint_level || hintLevel + 1);
    } catch (error) {
      setHint({
        hint: 'The tutor is currently unavailable. Try again in a moment.',
        explanation: error?.message || 'A fresh hint could not be generated.',
        concept: 'Retry',
        next_step: 'Refine your attempt and request a new hint.',
        hint_level: hintLevel,
        provider: 'rule_based',
        can_request_next_hint: false,
      });
    } finally {
      setHintLoading(false);
    }
  };

  if (questionsResource.loading && !questions.length) {
    return <div className="app-shell"><main className="panel page-state"><div className="page-state-inner"><Sparkles size={18} /><p>Loading practice problems…</p></div></main></div>;
  }

  if (questionsResource.error || !selectedQuestion) {
    return <div className="app-shell"><main className="panel page-state"><div className="page-state-inner text-error"><AlertCircle size={18} /><div><h2>Practice is unavailable</h2><p>{questionsResource.error?.message || 'No coding challenge is ready yet.'}</p></div></div></main></div>;
  }

  return (
    <div className="app-shell practice-shell">
      <header className="practice-topbar">
        <div>
          <span className="section-eyebrow"><Code2 size={12} /> STUDENT WORKSPACE</span>
          <h1>Practice studio</h1>
        </div>
        <div className="practice-toolbar">
          <label className="select-wrap">
            <span>Challenge</span>
            <select value={selectedQuestion.question_id} onChange={handleSelectQuestion}>
              {questions.map((question) => <option key={question.question_id} value={question.question_id}>{question.title}</option>)}
            </select>
          </label>
          <button className="ghost-button" onClick={() => navigate('/dashboard')} type="button">Back to dashboard</button>
        </div>
      </header>

      <main className="practice-layout">
        <aside className="panel problem-panel">
          <div className="problem-header">
            <span className={`difficulty-pill difficulty-${selectedQuestion.difficulty?.toLowerCase?.() || 'easy'}`}>{titleCase(selectedQuestion.difficulty)}</span>
            <span className="topic-pill">{titleCase(selectedQuestion.topic)}</span>
          </div>
          <h2>{selectedQuestion.title}</h2>
          <p>{selectedQuestion.description}</p>

          <div className="problem-meta">
            <div><small>Language</small><strong>{displayLanguage(selectedQuestion.language)}</strong></div>
            <div><small>Time limit</small><strong>{selectedQuestion.time_limit}s</strong></div>
            <div><small>Memory</small><strong>{selectedQuestion.memory_limit}MB</strong></div>
          </div>

          <div className="example-box">
            <h3>Sample input</h3>
            <pre>{selectedQuestion.sample_input}</pre>
          </div>
          <div className="example-box">
            <h3>Sample output</h3>
            <pre>{selectedQuestion.sample_output}</pre>
          </div>
          <div className="constraint-box">
            <h3>Constraints</h3>
            <ul>{selectedQuestion.constraints?.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
          </div>
        </aside>

        <section className="workspace-panel panel">
          <div className="editor-header">
            <div className="status-badge status-neutral">{displayLanguage(selectedQuestion.language)}</div>
            <div className="workspace-actions">
              <button className="secondary-button" onClick={() => requestHint(false)} disabled={hintLoading || !sourceCode.trim()} type="button">
                {hintLoading ? 'Thinking…' : 'Ask for hint'}
              </button>
              <button className="secondary-button" onClick={() => requestHint(true)} disabled={hintLoading || !sourceCode.trim()} type="button">Next hint</button>
              <button className="primary-button" onClick={runCode} disabled={running || !sourceCode.trim()} type="button">
                <Play size={15} /> {running ? 'Running…' : 'Run code'}
              </button>
            </div>
          </div>

          <div className="editor-grid">
            <div className="editor-card">
              <div className="editor-label-row">
                <span>Solution</span>
              </div>
              <textarea value={sourceCode} onChange={(event) => setSourceCode(event.target.value)} spellCheck={false} aria-label="Coding workspace editor" />
            </div>
            <div className="editor-card compact-card">
              <div className="editor-label-row">
                <span>Input</span>
              </div>
              <textarea value={stdin} onChange={(event) => setStdin(event.target.value)} rows={10} spellCheck={false} aria-label="Console input" />
            </div>
          </div>

          <div className={`result-card ${statusTone}`}>
            <div className="result-head">
              <span className="result-icon"><Terminal size={15} /></span>
              <strong>Execution result</strong>
            </div>
            {!result ? <p>Run your code to inspect the output and catch edge cases.</p> : (
              <>
                <div className="result-status-row">
                  <span className={`status-badge status-${statusTone}`}>{(result.status || 'pending').replaceAll('_', ' ')}</span>
                  {result.execution_time != null && <small>{result.execution_time}s</small>}
                </div>
                {result.stdout && <pre>{result.stdout}</pre>}
                {result.stderr && <pre className="error-output">{result.stderr}</pre>}
                {result.compile_output && <pre className="error-output">{result.compile_output}</pre>}
                {!result.stdout && !result.stderr && !result.compile_output && <p>No output returned.</p>}
              </>
            )}
          </div>

          <div className="hint-card">
            <div className="hint-head"><BrainCircuit size={16} /> <strong>AI tutor hint</strong></div>
            {hint ? <>
              <p><strong>{hint.concept}</strong></p>
              <p>{hint.hint}</p>
              <p>{hint.explanation}</p>
              <p className="hint-next-step"><ArrowRight size={15} /> {hint.next_step}</p>
              <small>Hint level {hint.hint_level} · {hint.provider}</small>
            </> : <p>Use a guided hint when you need a nudge in the right direction.</p>}
          </div>
        </section>
      </main>
    </div>
  );
}

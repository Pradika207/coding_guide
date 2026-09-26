import { AlertCircle, ArrowRight, BrainCircuit, CheckCircle2, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
  const [language, setLanguage] = useState(user?.selected_language || 'python');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  const startAssessment = async () => {
    setStarting(true);
    setError('');
    try {
      const preferred = language || user?.selected_language || 'python';
      await updateLanguage(preferred);
      const response = await api.startAssessment();
      if (response?.session_id) {
        navigate('/dashboard', { replace: true });
        return;
      }
      throw new Error('Assessment session could not be created.');
    } catch (caught) {
      setError(caught?.message || 'We could not begin the assessment right now.');
    } finally {
      setStarting(false);
    }
  };

  return <div className="app-shell">
    <main className="assessment-page">
      <section className="panel assessment-panel">
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

            {error && <div className="inline-error"><AlertCircle size={15} /> {error}</div>}
          </div>
        </div>
      </section>
    </main>
  </div>;
}

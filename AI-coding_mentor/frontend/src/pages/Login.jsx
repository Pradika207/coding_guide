import { useState } from 'react';
import { ArrowRight, Code2, LockKeyhole, Sparkles } from 'lucide-react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function Login() {
  const { user, login, sessionExpired } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (failure) {
      setError(failure.message || 'Unable to sign in. Check your details and try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="login-page">
    <section className="login-aside">
      <a className="brand login-brand" href="/login"><span className="brand-mark"><Code2 size={19} /></span><span className="brand-copy">code<span>mentor</span></span></a>
      <div className="login-aside-copy"><span className="aside-chip"><Sparkles size={13} /> YOUR NEXT CHAPTER</span><h1>Progress is built<br />one problem at a time.</h1><p>Find your rhythm, grow your skills, and make every practice session count.</p><div className="aside-decoration"><span>{'{ }'}</span><i /><i /><i /></div></div>
      <span className="login-aside-footer">A thoughtful space for your coding journey.</span>
    </section>
    <section className="login-content">
      <div className="login-card">
        <div className="login-mobile-brand"><span className="brand-mark"><Code2 size={18} /></span><span className="brand-copy">code<span>mentor</span></span></div>
        <span className="form-eyebrow">WELCOME BACK</span>
        <h2>Sign in to your space</h2>
        <p className="login-subtitle">Your learning journey is right where you left it.</p>
        {sessionExpired && <div className="inline-alert" role="status">Your session expired. Sign in again to continue.</div>}
        {error && <div className="inline-alert" role="alert">{error}</div>}
        <form onSubmit={handleSubmit} className="login-form">
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
          <div className="password-label"><label htmlFor="password">Password</label></div>
          <div className="password-input"><LockKeyhole size={16} /><input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required /></div>
          <button className="button button-dark login-submit" type="submit" disabled={submitting}>{submitting ? 'Signing you in…' : 'Sign in'} <ArrowRight size={16} /></button>
        </form>
        <p className="login-footnote">Your account is protected. We never display your credentials.</p>
      </div>
      <span className="login-copyright">© AI Coding Mentor · Keep learning, keep building.</span>
    </section>
  </main>;
}

import { Bell, ChevronDown, Code2, LogOut } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';

const demoNotifications = [
  { id: 1, title: 'New lesson available', detail: 'Arrays fundamentals has a fresh walkthrough.' },
  { id: 2, title: 'Streak reminder', detail: 'You are 2 sessions away from a 7-day streak.' },
  { id: 3, title: 'Assessment unlocked', detail: 'Your next challenge is ready to start.' },
];

export default function DashboardHeader() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const initials = (user?.name || user?.email || 'S').split(/[\s@]/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('');

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="topbar">
      <a className="brand" href="/dashboard" aria-label="AI Coding Mentor dashboard">
        <span className="brand-mark"><Code2 size={19} strokeWidth={2.5} /></span>
        <span className="brand-copy">code<span>mentor</span></span>
      </a>
      <nav className="main-nav" aria-label="Main navigation">
        <a className="nav-link active" href="/dashboard">Dashboard</a>
        <a className="nav-link" href="/learn">Learn</a>
        <a className="nav-link" href="/dashboard#practice">Practice</a>
        <a className="nav-link" href="/dashboard#progress">Progress</a>
        {user?.role === 'admin' && <a className="nav-link" href="/admin">Admin</a>}
      </nav>
      <div className="topbar-actions" ref={panelRef}>
        <span className="nav-streak"><span aria-hidden="true">✦</span> Keep your streak alive</span>
        <button
          className="icon-button notification-button"
          type="button"
          aria-label="Notifications"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          <Bell size={18} />
          <i />
        </button>
        {open && (
          <div className="notification-panel" role="dialog" aria-label="Notifications">
            <div className="notification-panel-header">
              <strong>Notifications</strong>
              <span>3 new</span>
            </div>
            <div className="notification-list">
              {demoNotifications.map((item) => (
                <div className="notification-item" key={item.id}>
                  <strong>{item.title}</strong>
                  <span>{item.detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="user-menu">
          <span className="avatar" aria-hidden="true">{initials}</span>
          <span className="user-menu-name">{user?.name || 'Student'}</span>
          <ChevronDown size={15} className="user-chevron" />
          <button type="button" className="logout-button" onClick={logout} aria-label="Log out" title="Log out"><LogOut size={16} /></button>
        </div>
      </div>
    </header>
  );
}

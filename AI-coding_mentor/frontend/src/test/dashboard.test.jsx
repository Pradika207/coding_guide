import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

const currentUser = {
  user_id: 'student-1',
  name: 'Pradika Student',
  email: 'pradika@example.test',
  selected_language: 'python',
  created_at: '2026-01-01T00:00:00Z',
};

const responses = {
  '/auth/me': currentUser,
  '/auth/language': { selected_language: 'python' },
  '/gamification': { total_xp: 1240, level: 4, current_streak: 7, longest_streak: 11, daily_goal_xp: 100, daily_xp: 80, daily_goal_progress: 0.8, daily_goal_completed: false },
  '/gamification/badges': [{ badge_id: 'first-lesson', name: 'First Steps', description: 'Complete your first lesson', criteria_type: 'lesson_completed', criteria_value: 1, icon: 'book', earned_at: '2026-03-01T12:00:00Z' }],
  '/gamification/xp-history?limit=8': [{ event_id: 'evt-1', event_type: 'lesson_completed', source_id: 'lesson-1', xp_amount: 10, created_at: '2026-03-01T12:00:00Z' }],
  '/roadmap': { roadmap_id: 'map-1', user_id: 'student-1', language: 'python', source_assessment_id: 'assess-1', current_topic: 'arrays', topics: [{ topic: 'fundamentals', order: 1, status: 'completed', score: 91 }, { topic: 'arrays', order: 2, status: 'current', score: null }, { topic: 'sorting', order: 3, status: 'pending', score: null }], created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  '/roadmap/current': { topic: 'arrays', status: 'current', reason: 'Recommended next by your assessment' },
  '/lessons/current': { lesson_id: 'lesson-2', topic: 'arrays', title: 'Traversing an Array', progress: 35, status: 'in_progress' },
  '/lessons/lesson-2': { lesson_id: 'lesson-2', topic: 'arrays', title: 'Traversing an Array', description: 'Learn how arrays work through direct indexing and iteration.', content: [{ type: 'concept', title: 'Array access', text: 'Array elements are accessed by their index.' }, { type: 'example', title: 'Example', text: 'numbers[0] gives the first value in the array.' }], quiz_ids: ['quiz-2'], question_ids: ['q-arrays-2'] },
  '/lessons/lesson-2/quiz': { quiz_id: 'quiz-2', question: 'Which term describes selecting a single item from an array by position?', options: ['Index', 'Loop', 'Function', 'Boolean'], correct_option: 'Index', explanation: 'Indexing uses a position to address a specific item.' },
  '/lessons/lesson-2/quiz/complete': { quiz_id: 'quiz-2', score: 100, total_questions: 1, correct_answers: 1, passed: true, xp_awarded: 25 },
  '/lessons/progress/arrays': { topic: 'arrays', total_lessons: 4, completed_lessons: 1, progress_percent: 25 },
  '/recommendations/current?limit=4': { status: 'ready', message: null, language: 'python', recommendations: [{ recommendation_id: 'rec-1', question_id: 'q-1', title: 'Find the Maximum', topic: 'arrays', difficulty: 'easy', score: 85, reason: 'Arrays is a developing topic for you.' }], generated_at: '2026-03-01T00:00:00Z' },
  '/ml/skill-profile': { status: 'ready', language: 'python', topics: [{ topic: 'arrays', predicted_skill: 'intermediate', confidence: 0.82, rule_based_skill: 'beginner', status: 'predicted' }] },
  '/assessment/history': [{ session_id: 'session-1', language: 'python', score: 78, skill_level: 'intermediate', created_at: '2026-03-01T00:00:00Z' }],
  '/assessment/session-1/result': { result_id: 'result-1', session_id: 'session-1', language: 'python', overall_score: 78, accuracy: 78, skill_level: 'intermediate', topic_scores: { arrays: 64 }, strong_topics: ['fundamentals'], weak_topics: ['arrays'], recommended_next_topic: 'arrays', created_at: '2026-03-01T00:00:00Z' },
};

function setupFetch({ overrides = {}, failures = [], failureStatus = 503 } = {}) {
  global.fetch = vi.fn(async (url) => {
    const parsed = new URL(url);
    const key = `${parsed.pathname}${parsed.search}`;
    const route = parsed.pathname;
    if (failures.includes(key) || failures.includes(route)) return new Response(JSON.stringify({ detail: 'private backend error' }), { status: failureStatus, headers: { 'Content-Type': 'application/json' } });
    if (Object.hasOwn(overrides, key) && overrides[key]?.__status) return new Response(JSON.stringify(overrides[key].body || {}), { status: overrides[key].__status, headers: { 'Content-Type': 'application/json' } });
    if (Object.hasOwn(overrides, route) && overrides[route]?.__status) return new Response(JSON.stringify(overrides[route].body || {}), { status: overrides[route].__status, headers: { 'Content-Type': 'application/json' } });
    const body = Object.hasOwn(overrides, key) ? overrides[key] : Object.hasOwn(overrides, route) ? overrides[route] : responses[key] ?? responses[route];
    if (body === undefined) return new Response(JSON.stringify({ detail: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
}

function renderApp(initialEntry = '/dashboard') {
  return render(<MemoryRouter initialEntries={[initialEntry]}><App /></MemoryRouter>);
}

describe('student dashboard', () => {
  beforeEach(() => {
    window.sessionStorage.setItem('acm_access_token', 'test-token');
    setupFetch();
  });
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders the dashboard and greets with the authenticated user name', async () => {
    renderApp();
    expect(await screen.findByRole('heading', { name: /good to see you, pradika/i })).toBeInTheDocument();
    expect(screen.getByText('Your learning path')).toBeInTheDocument();
  });

  it('renders the assessment entry page from the dashboard CTA', async () => {
    render(<MemoryRouter initialEntries={['/assessment']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /start your assessment/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /begin assessment/i })).toBeInTheDocument();
  });

  it('starts the assessment with the selected language', async () => {
    const user = userEvent.setup();
    setupFetch({
      overrides: {
        '/auth/language': { message: 'Programming language updated successfully', user: { ...currentUser, selected_language: 'javascript' } },
        '/assessment/start': { session_id: 'assess-2', language: 'javascript', status: 'in_progress', questions: [] },
      },
    });
    render(<MemoryRouter initialEntries={['/assessment']}><App /></MemoryRouter>);

    const languageField = await screen.findByLabelText('Choose a language');
    await user.selectOptions(languageField, 'javascript');
    await user.click(await screen.findByRole('button', { name: /begin assessment/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/auth/language'), expect.objectContaining({ method: 'PUT' }));
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/assessment/start'), expect.objectContaining({ method: 'POST' }));
    });
  });

  it('renders gamification values from the backend', async () => {
    renderApp();
    expect(await screen.findByText('1,240')).toBeInTheDocument();
    expect(screen.getByText('7 days')).toBeInTheDocument();
    expect(screen.getByText('80 / 100 XP')).toBeInTheDocument();
  });

  it('renders roadmap, personalized problem, badges and real XP activity', async () => {
    renderApp();
    expect(await screen.findByText('Traversing an Array', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Find the Maximum')).toBeInTheDocument();
    expect(screen.getByText('Arrays is a developing topic for you.')).toBeInTheDocument();
    expect(screen.getByText('First Steps')).toBeInTheDocument();
    expect(screen.getByText('Lesson completed')).toBeInTheDocument();
  });

  it('renders rule-based assessment and distinct ML estimate', async () => {
    renderApp();
    expect(await screen.findByText('Intermediate')).toBeInTheDocument();
    expect(screen.getByText('ML SKILL ESTIMATE')).toBeInTheDocument();
    expect(screen.getByText('A model estimate, not a guaranteed measure of ability.')).toBeInTheDocument();
  });

  it('shows ML unavailable state without inventing a prediction', async () => {
    setupFetch({ failures: ['/ml/skill-profile'] });
    renderApp();
    expect(await screen.findByText('ML skill prediction unavailable')).toBeInTheDocument();
  });

  it('shows independent section errors while preserving loaded dashboard data', async () => {
    setupFetch({ failures: ['/gamification'] });
    renderApp();
    expect(await screen.findByText('Progress data is taking a break.')).toBeInTheDocument();
    expect(await screen.findByText('Find the Maximum')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /good to see you, pradika/i })).toBeInTheDocument();
  });

  it('shows new-student empty states when no roadmap, assessment, or activity exists', async () => {
    setupFetch({ overrides: {
      '/roadmap': { __status: 404, body: { detail: 'roadmap not found' } },
      '/roadmap/current': { __status: 404, body: { detail: 'roadmap not found' } },
      '/lessons/current': { __status: 404, body: { detail: 'lesson not found' } },
      '/assessment/history': [],
      '/gamification/xp-history?limit=8': [],
      '/recommendations/current?limit=4': { status: 'assessment_required', recommendations: [], message: 'Complete an assessment first.' },
      '/ml/skill-profile': { status: 'insufficient_data', message: 'Complete more activity.', topics: [] },
    } });
    renderApp();
    expect(await screen.findByText('Take your coding assessment to unlock a personalized learning path.')).toBeInTheDocument();
    expect(screen.getByText('Start your first lesson to build your learning history.')).toBeInTheDocument();
    expect(screen.getByText('Complete a coding assessment to see your rule-based level and strong topics.')).toBeInTheDocument();
  });

  it('shows a helpful recommendation empty state for missing language or assessment data instead of a generic load error', async () => {
    setupFetch({
      overrides: {
        '/recommendations/current?limit=4': { __status: 400, body: { detail: 'Select a programming language before requesting recommendations' } },
      },
    });
    renderApp();
    expect(await screen.findByText('Personalize your practice')).toBeInTheDocument();
    expect(screen.queryByText('Unable to load this section. Try again.')).not.toBeInTheDocument();
  });

  it('redirects an unauthenticated visitor to login and clears expired session tokens', async () => {
    window.sessionStorage.clear();
    setupFetch();
    renderApp();
    expect(await screen.findByRole('heading', { name: 'Sign in to your space' })).toBeInTheDocument();

    cleanup();
    window.sessionStorage.setItem('acm_access_token', 'expired');
    setupFetch({ failures: ['/auth/me'], failureStatus: 401 });
    renderApp();
    expect(await screen.findByText('Your session expired. Sign in again to continue.')).toBeInTheDocument();
    await waitFor(() => expect(window.sessionStorage.getItem('acm_access_token')).toBeNull());
  });

  it('logs out without showing the token and returns to login', async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByText('Your learning path');
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in to your space' })).toBeInTheDocument();
    expect(window.sessionStorage.getItem('acm_access_token')).toBeNull();
  });

  it('renders the protected Learn page and roadmap journey', async () => {
    render(<MemoryRouter initialEntries={['/learn']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /your coding journey/i })).toBeInTheDocument();
    expect(screen.getByText('Arrays')).toBeInTheDocument();
    expect(screen.getByText('Continue')).toBeInTheDocument();
  });

  it('loads a lesson and supports quiz submission', async () => {
    render(<MemoryRouter initialEntries={['/learn/lesson/lesson-2']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /traversing an array/i })).toBeInTheDocument();

    const option = await screen.findByRole('button', { name: /index/i });
    await userEvent.click(option);
    await userEvent.click(screen.getByRole('button', { name: /submit answer/i }));

    expect(await screen.findByText('Correct!')).toBeInTheDocument();
    expect(screen.getByText(/\+\d+ XP/i)).toBeInTheDocument();
  });

  it('opens the protected coding workspace and runs a challenge', async () => {
    setupFetch({
      overrides: {
        '/questions?language=python': {
          questions: [{
            question_id: 'python-arrays-1',
            title: 'Find the Maximum',
            description: 'Return the highest value from a list.',
            language: 'python',
            topic: 'arrays',
            difficulty: 'easy',
            sample_input: '3\n5 2 9',
            sample_output: '9',
            constraints: ['1 <= n <= 1000'],
            time_limit: 2,
            memory_limit: 256,
          }],
        },
        '/code/execute': {
          status: 'accepted',
          stdout: '9\n',
          stderr: '',
          compile_output: '',
          execution_time: 0.12,
          memory: 128,
        },
        '/tutor/hint': {
          hint: 'Start by iterating through the list and tracking the largest seen value.',
          explanation: 'A running maximum helps you compare each value in order.',
          concept: 'Tracking state',
          next_step: 'Update the maximum as you read each item.',
          hint_level: 1,
          provider: 'rule_based',
          can_request_next_hint: true,
        },
      },
    });

    render(<MemoryRouter initialEntries={['/practice/python-arrays-1']}><App /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: /practice studio/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /find the maximum/i })).toBeInTheDocument();

    const runButton = screen.getByRole('button', { name: /run code/i });
    await userEvent.click(runButton);

    expect(await screen.findByText('accepted')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /ask for hint/i }));
    expect(await screen.findByText('Tracking state')).toBeInTheDocument();
  });
});

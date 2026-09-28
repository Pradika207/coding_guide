import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

const roadmapTopics = ['fundamentals', 'variables', 'conditionals', 'loops', 'functions', 'arrays', 'strings', 'searching', 'sorting', 'recursion', 'linked_lists', 'stack', 'queue', 'hashing', 'trees', 'graphs', 'dynamic_programming', 'object_oriented_programming'];

const responses = {
  '/auth/me': currentUser,
  '/auth/language': { selected_language: 'python' },
  '/gamification': { total_xp: 1240, level: 4, current_streak: 7, longest_streak: 11, daily_goal_xp: 100, daily_xp: 80, daily_goal_progress: 0.8, daily_goal_completed: false },
  '/gamification/badges': [{ badge_id: 'first-lesson', name: 'First Steps', description: 'Complete your first lesson', criteria_type: 'lesson_completed', criteria_value: 1, icon: 'book', earned_at: '2026-03-01T12:00:00Z' }],
  '/gamification/xp-history?limit=8': [{ event_id: 'evt-1', event_type: 'lesson_completed', source_id: 'lesson-1', xp_amount: 10, created_at: '2026-03-01T12:00:00Z' }],
  '/roadmap': { roadmap_id: 'map-1', user_id: 'student-1', language: 'python', source_assessment_id: 'assess-1', current_topic: 'arrays', topics: roadmapTopics.map((topic, index) => ({ topic, order: index + 1, status: index === 0 ? 'completed' : index === 1 ? 'unlocked' : index === 5 ? 'recommended' : 'locked', score: index === 0 ? 91 : index === 5 ? 64 : null })), created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  '/roadmap/generate': { roadmap_id: 'map-2', user_id: 'student-1', language: 'javascript', source_assessment_id: 'assess-2', current_topic: 'fundamentals', topics: [{ topic: 'fundamentals', order: 1, status: 'recommended', score: null }], created_at: '2026-03-02T00:00:00Z', updated_at: '2026-03-02T00:00:00Z' },
  '/roadmap/current': { topic: 'arrays', status: 'current', reason: 'Recommended next by your assessment' },
  '/lessons/current': { lesson_id: 'lesson-2', topic: 'arrays', title: 'Traversing an Array', progress: 35, status: 'in_progress' },
  '/lessons/lesson-2': { lesson_id: 'lesson-2', topic: 'arrays', title: 'Traversing an Array', description: 'Learn how arrays work through direct indexing and iteration.', content: [{ type: 'concept', title: 'Array access', text: 'Array elements are accessed by their index.' }, { type: 'example', title: 'Example', text: 'numbers[0] gives the first value in the array.' }], quiz_ids: ['quiz-2'], question_ids: ['q-arrays-2'] },
  '/lessons/lesson-2/quiz': { quiz_id: 'quiz-2', question: 'Which term describes selecting a single item from an array by position?', options: ['Index', 'Loop', 'Function', 'Boolean'], correct_option: 'Index', explanation: 'Indexing uses a position to address a specific item.' },
  '/lessons/lesson-2/quiz/complete': { quiz_id: 'quiz-2', score: 100, total_questions: 1, correct_answers: 1, passed: true, xp_awarded: 25 },
  '/lessons/progress/arrays': { topic: 'arrays', total_lessons: 4, completed_lessons: 1, progress_percent: 25 },
  '/lessons/progress/variables': { topic: 'variables', total_lessons: 4, completed_lessons: 1, progress_percent: 25 },
  '/lessons?topic=variables': [{ lesson_id: 'lesson-2', topic: 'variables', title: 'Traversing an Array', status: 'in_progress' }],
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
        '/assessment/start': { session_id: 'assess-2', language: 'javascript', status: 'in_progress', questions: Array.from({ length: 5 }, (_, index) => ({ question_id: `q-assess-${index + 1}`, title: `Challenge ${index + 1}`, description: `Solve challenge ${index + 1}.`, topic: 'strings', difficulty: 'easy', sample_input: 'hello', sample_output: 'olleh', constraints: [] })) },
        '/assessment/assess-2/submit': { question_id: 'q-assess-1', status: 'accepted', stdout: '', stderr: '', compile_output: '', attempt_number: 2 },
        '/assessment/assess-2/complete': { session_id: 'assess-2', status: 'completed', score: 0, total_questions: 5, solved_questions: 0, accuracy: 0, language: 'javascript' },
        '/assessment/assess-2/result': { result_id: 'result-assess-2', session_id: 'assess-2', language: 'javascript', overall_score: 0, accuracy: 0, skill_level: 'beginner', topic_scores: { strings: 0 }, strong_topics: [], weak_topics: ['strings'], recommended_next_topic: 'Strings', created_at: '2026-03-02T00:00:00Z' },
      },
    });
    render(<MemoryRouter initialEntries={['/assessment']}><App /></MemoryRouter>);
    const normalFetch = global.fetch;
    const submitResults = [
      { question_id: 'q-assess-1', status: 'wrong_answer', stdout: '', stderr: '', compile_output: '', attempt_number: 1 },
      ...Array.from({ length: 5 }, (_, index) => ({ question_id: `q-assess-${Math.min(index + 1, 5)}`, status: 'accepted', stdout: '', stderr: '', compile_output: '', attempt_number: index === 0 ? 2 : 1 })),
    ];
    global.fetch = vi.fn((url, options) => {
      if (new URL(url).pathname.endsWith('/submit')) {
        return Promise.resolve(new Response(JSON.stringify(submitResults.shift()), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return normalFetch(url, options);
    });

    const languageField = await screen.findByLabelText('Choose a language');
    await user.selectOptions(languageField, 'javascript');
    await user.click(await screen.findByRole('button', { name: /begin assessment/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/auth/language'), expect.objectContaining({ method: 'PUT' }));
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/assessment/start'), expect.objectContaining({ method: 'POST' }));
    });
    expect(await screen.findByRole('heading', { name: 'Challenge 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /good to see you/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: 'Your solution' }), { target: { value: 'function solve() { return "olleh"; }' } });
    await user.click(screen.getByRole('button', { name: /submit answer/i }));
    expect(await screen.findByRole('status')).toHaveTextContent('wrong answer');
    expect(screen.queryByRole('button', { name: /next question/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /submit answer/i }));
    expect(await screen.findByRole('status')).toHaveTextContent('accepted');
    await user.click(screen.getByRole('button', { name: /next question/i }));
    for (let questionNumber = 2; questionNumber <= 5; questionNumber += 1) {
      expect(await screen.findByRole('heading', { name: `Challenge ${questionNumber}` })).toBeInTheDocument();
      fireEvent.change(screen.getByRole('textbox', { name: 'Your solution' }), { target: { value: 'function solve() { return "olleh"; }' } });
      await user.click(screen.getByRole('button', { name: /submit answer/i }));
      expect(await screen.findByRole('status')).toHaveTextContent('accepted');
      if (questionNumber < 5) await user.click(screen.getByRole('button', { name: /next question/i }));
    }
    expect(screen.queryByRole('button', { name: /finish assessment/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /finish assessment/i }));
    expect(await screen.findByRole('heading', { name: /your results are ready/i })).toBeInTheDocument();
    expect(screen.getByText('Score: 0%')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /view your learning path/i })).toHaveAttribute('href', '/learn');
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/assessment/assess-2/submit'), expect.objectContaining({ method: 'POST' }));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/assessment/assess-2/complete'), expect.objectContaining({ method: 'POST' }));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/assessment/assess-2/result'), expect.objectContaining({ method: 'GET' }));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/roadmap/generate'), expect.objectContaining({ method: 'POST' }));
    const requestPaths = global.fetch.mock.calls.map(([url]) => new URL(url).pathname);
    expect(requestPaths.indexOf('/assessment/assess-2/result')).toBeLessThan(requestPaths.indexOf('/roadmap/generate'));
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
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/learn']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Learning Path' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fundamentals, completed/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /variables, unlocked/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /arrays, ai recommended/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /arrays, ai recommended/i }).closest('.learning-map-node')).toHaveClass('is-active');
    expect(screen.getByRole('button', { name: /sorting, locked/i })).toBeDisabled();
    expect(document.querySelector('.is-final-level')).toHaveTextContent('FINAL CHALLENGE');
    expect(screen.getByText('not tracked')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /sorting, locked/i }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText('Coding Valley')).toBeInTheDocument();
    expect(screen.getByText('Data Structure Forest')).toBeInTheDocument();
    expect(screen.getByText('Algorithm Mountains')).toBeInTheDocument();
    expect(screen.getByText('Advanced Observatory')).toBeInTheDocument();
    expect(document.querySelectorAll('.learning-map-path path')).toHaveLength((roadmapTopics.length - 1) * 2);
    expect(document.querySelectorAll('.path-completed').length).toBeGreaterThan(0);
    expect(document.querySelectorAll('.path-future').length).toBeGreaterThan(0);
    const nodePositions = [...document.querySelectorAll('.learning-map-node')].map((node) => Number.parseFloat(node.style.left));
    expect(new Set(nodePositions).size).toBeGreaterThan(8);

    await user.click(screen.getByRole('button', { name: /arrays, ai recommended/i }));
    expect(await screen.findByRole('dialog', { name: 'Arrays' })).toHaveTextContent('AI RECOMMENDED');
    await user.click(screen.getByRole('button', { name: /close level details/i }));

    await user.click(screen.getByRole('button', { name: /variables, unlocked/i }));
    expect(await screen.findByRole('dialog', { name: 'Variables' })).toBeInTheDocument();
    expect(screen.getByText('1 of 4 lessons complete')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: /start learning/i }));
    expect(await screen.findByRole('heading', { name: /traversing an array/i })).toBeInTheDocument();
  });

  it('shows a loading state while the real roadmap request is pending', async () => {
    setupFetch();
    let resolveRoadmap;
    const roadmapRequest = new Promise((resolve) => { resolveRoadmap = resolve; });
    const fallbackFetch = global.fetch;
    global.fetch = vi.fn((url, options) => new URL(url).pathname === '/roadmap' ? roadmapRequest : fallbackFetch(url, options));

    render(<MemoryRouter initialEntries={['/learn']}><App /></MemoryRouter>);
    expect(await screen.findByText('Loading your real learning path…')).toBeInTheDocument();
    resolveRoadmap(new Response(JSON.stringify(responses['/roadmap']), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    expect(await screen.findByRole('button', { name: /arrays, ai recommended/i })).toBeInTheDocument();
  });

  it('shows a real assessment prompt instead of inventing levels when no roadmap exists', async () => {
    setupFetch({ overrides: { '/roadmap': { __status: 404, body: { detail: 'roadmap not found' } } } });
    render(<MemoryRouter initialEntries={['/learn']}><App /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Your adventure starts here' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /take assessment/i })).toHaveAttribute('href', '/assessment');
    expect(document.querySelector('.has-empty-world .empty-world-art')).toBeInTheDocument();
    expect(document.querySelectorAll('.learning-map-node')).toHaveLength(0);
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

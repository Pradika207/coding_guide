const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const TOKEN_KEY = 'acm_access_token';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const tokenStore = {
  get: () => window.sessionStorage.getItem(TOKEN_KEY),
  set: (token) => window.sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => window.sessionStorage.removeItem(TOKEN_KEY),
};

const messages = {
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have access to this information.',
  404: 'This information is not available right now.',
  422: 'Some of the submitted information needs checking.',
  500: 'We could not load this right now. Please try again.',
};

async function request(path, { method = 'GET', body, auth = true, signal, allowServiceUnavailableDetail = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = auth ? tokenStore.get() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(0, 'We could not connect. Check your connection and try again.');
  }

  if (response.status === 401 && auth) {
    tokenStore.clear();
    window.dispatchEvent(new CustomEvent('acm:session-expired'));
  }
  if (!response.ok) {
    let detail;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === 'string' ? payload.detail : null;
    } catch {
      detail = null;
    }
    const safeMessage = response.status === 401 && !auth
      ? 'Email or password could not be verified.'
      : response.status === 503 && allowServiceUnavailableDetail && detail
        ? detail
        : response.status >= 500
        ? 'We could not load this right now. Please try again.'
        : messages[response.status] || detail || 'Something went wrong. Please try again.';
    throw new ApiError(response.status, safeMessage);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  login: (credentials) => request('/auth/login', { method: 'POST', body: credentials, auth: false }),
  me: () => request('/auth/me'),
  language: () => request('/auth/language'),
  selectLanguage: (language) => request('/auth/language', { method: 'PUT', body: { language } }),
  startAssessment: () => request('/assessment/start', { method: 'POST' }),
  submitAssessmentCode: (sessionId, payload) => request(`/assessment/${encodeURIComponent(sessionId)}/submit`, { method: 'POST', body: payload, allowServiceUnavailableDetail: true }),
  completeAssessment: (sessionId) => request(`/assessment/${encodeURIComponent(sessionId)}/complete`, { method: 'POST' }),
  roadmap: () => request('/roadmap'),
  getRoadmap: () => request('/roadmap'),
  generateRoadmap: () => request('/roadmap/generate', { method: 'POST' }),
  currentRoadmapTopic: () => request('/roadmap/current'),
  currentLesson: () => request('/lessons/current'),
  getCurrentLesson: () => request('/lessons/current'),
  getLessons: (params = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') search.append(key, String(value));
    });
    const query = search.toString();
    return request(query ? `/lessons?${query}` : '/lessons');
  },
  getLesson: (lessonId) => request(`/lessons/${encodeURIComponent(lessonId)}`),
  startLesson: (lessonId) => request(`/lessons/${encodeURIComponent(lessonId)}/start`, { method: 'POST' }),
  completeLesson: (lessonId) => request(`/lessons/${encodeURIComponent(lessonId)}/complete`, { method: 'POST' }),
  getLessonQuiz: (lessonId) => request(`/lessons/${encodeURIComponent(lessonId)}/quiz`),
  completeQuiz: (lessonId, quizId, selectedOption) => request(`/lessons/${encodeURIComponent(lessonId)}/quiz/complete`, {
    method: 'POST',
    body: { quiz_id: quizId, selected_option: selectedOption },
  }),
  getTopicProgress: (topic) => request(`/lessons/progress/${encodeURIComponent(topic)}`),
  lessonProgress: (topic) => request(`/lessons/progress/${encodeURIComponent(topic)}`),
  getQuestions: (params = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') search.append(key, String(value));
    });
    const query = search.toString();
    return request(query ? `/questions?${query}` : '/questions');
  },
  getQuestion: (questionId) => request(`/questions/${encodeURIComponent(questionId)}`),
  executeCode: (payload) => request('/code/execute', { method: 'POST', body: payload }),
  submitCode: (payload) => request('/code/execute', { method: 'POST', body: payload }),
  getTutorHint: (payload) => request('/tutor/hint', { method: 'POST', body: payload }),
  getNextTutorHint: (payload) => request('/tutor/next-hint', { method: 'POST', body: payload }),
  gamification: () => request('/gamification'),
  badges: () => request('/gamification/badges'),
  xpHistory: () => request('/gamification/xp-history?limit=8'),
  recommendations: () => request('/recommendations/current?limit=4'),
  skillProfile: () => request('/ml/skill-profile'),
  assessmentHistory: () => request('/assessment/history'),
  assessmentResult: (sessionId) => request(`/assessment/${encodeURIComponent(sessionId)}/result`),
  adminOverview: () => request('/admin/overview'),
  adminHealth: () => request('/admin/health'),
  adminMonitoring: () => request('/admin/ml/monitoring'),
  adminRetraining: () => request('/admin/ml/retraining'),
  adminDvc: () => request('/admin/dvc'),
  adminMlflow: () => request('/admin/mlflow'),
};

export const apiBaseUrl = API_BASE_URL;

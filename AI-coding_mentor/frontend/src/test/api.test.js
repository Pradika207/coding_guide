import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, tokenStore } from '../services/api';

afterEach(() => {
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe('dashboard API client', () => {
  it('adds the session token only to authenticated API requests', async () => {
    tokenStore.set('private-session-token');
    global.fetch = vi.fn().mockImplementation(() => new Response(JSON.stringify({ user_id: 'u1' }), { status: 200 }));

    await api.me();
    await api.login({ email: 'student@example.test', password: 'private-password' });

    expect(global.fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer private-session-token');
    expect(global.fetch.mock.calls[1][1].headers.Authorization).toBeUndefined();
  });

  it('maps API failures to safe status-bearing errors', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'internal trace' }), { status: 403 }));
    await expect(api.me()).rejects.toMatchObject({ name: 'ApiError', status: 403, message: 'You do not have access to this information.' });
  });

  it('shows the sanitized 503 reason when assessment code execution is unavailable', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Code execution service is not configured' }), { status: 503 }));

    await expect(api.submitAssessmentCode('session-1', { question_id: 'q1', source_code: 'print(1)', stdin: '' }))
      .rejects.toMatchObject({ status: 503, message: 'Code execution service is not configured' });
  });

  it('clears an expired token and dispatches session-expired on 401', async () => {
    tokenStore.set('expired-token');
    const onExpired = vi.fn();
    window.addEventListener('acm:session-expired', onExpired);
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 }));

    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    expect(tokenStore.get()).toBeNull();
    expect(onExpired).toHaveBeenCalledOnce();
    window.removeEventListener('acm:session-expired', onExpired);
  });

  it('maps network failures without exposing raw details', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('socket with secret token failed'));
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
    await expect(api.me()).rejects.toMatchObject({ status: 0, message: 'We could not connect. Check your connection and try again.' });
  });
});

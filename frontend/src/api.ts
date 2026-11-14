import type { ActivityPage, Snack, SnackInput, SnackPage, Summary, User } from './types';

const BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(path: string, token?: string | null, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.');
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const issue = payload?.error;
    throw new ApiError(response.status, issue?.code || 'REQUEST_FAILED', issue?.message || 'Something went wrong.');
  }
  return payload as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>('/auth/login', null, {
      method: 'POST', body: JSON.stringify({ email, password }),
    }),
  register: (name: string, email: string, password: string) =>
    request<{ token: string; user: User }>('/auth/register', null, {
      method: 'POST', body: JSON.stringify({ name, email, password }),
    }),
  me: (token: string) => request<User>('/auth/me', token),
  logout: (token: string) => request<void>('/auth/logout', token, { method: 'POST' }),
  snacks: (token: string, params: URLSearchParams) => request<SnackPage>(`/snacks?${params.toString()}`, token),
  summary: (token: string) => request<Summary>('/snacks/summary', token),
  create: (token: string, data: SnackInput) =>
    request<Snack>('/snacks', token, { method: 'POST', body: JSON.stringify(data) }),
  edit: (token: string, id: number, data: Partial<SnackInput>) =>
    request<Snack>(`/snacks/${id}`, token, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (token: string, id: number) => request<void>(`/snacks/${id}`, token, { method: 'DELETE' }),
  consume: (token: string, id: number, amount: number) =>
    request<Snack>(`/snacks/${id}/consume`, token, { method: 'POST', body: JSON.stringify({ amount }) }),
  restock: (token: string, id: number, amount: number) =>
    request<Snack>(`/snacks/${id}/restock`, token, { method: 'POST', body: JSON.stringify({ amount }) }),
  vote: (token: string, id: number) => request<Snack>(`/snacks/${id}/vote`, token, { method: 'POST' }),
  unvote: (token: string, id: number) => request<Snack>(`/snacks/${id}/vote`, token, { method: 'DELETE' }),
  activity: (token: string, page: number) => request<ActivityPage>(`/activity?page=${page}&page_size=10`, token),
};

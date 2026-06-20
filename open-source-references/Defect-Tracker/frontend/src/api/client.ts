const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function getAuthToken(): string | null {
    return localStorage.getItem('auth_token');
}

async function request<T>(
    path: string,
    options: RequestInit = {}
):  Promise<T> {
    const token = getAuthToken();

    const response = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {} ),
            ...options.headers     
        },
    });
    if (response.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || `Request failed: ${response.status}`);
    }

    return response.json();
}

export const apiClient = {
    get: <T>(path: string) => request<T>(path, { method: 'GET' }),

  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  postForm: <T>(path: string, body: Record<string, string>) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(body).toString(),
    }),

  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),

  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};


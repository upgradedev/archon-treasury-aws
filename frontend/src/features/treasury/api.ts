let activeCsrfToken: string | null = null;

export function setCsrfToken(token: string | null | undefined): void {
  if (token) {
    activeCsrfToken = token;
  }
}

export async function requestJson<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    if (activeCsrfToken) {
      headers['X-CSRF-Token'] = activeCsrfToken;
    }
  }
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    credentials: 'same-origin',
    headers: Object.keys(headers).length > 0 ? headers : undefined,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Service returned an unreadable response (${response.status}).`);
  }
  if (data && typeof data === 'object' && 'session' in data) {
    const sess = (data as { session?: { csrf_token?: string } }).session;
    if (sess?.csrf_token) {
      activeCsrfToken = sess.csrf_token;
    }
  }
  if (!response.ok) {
    const error =
      data && typeof data === 'object' && 'error' in data
        ? String((data as { error: unknown }).error)
        : `Service refused the request (${response.status}).`;
    throw new Error(error);
  }
  return data as T;
}

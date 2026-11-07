export async function requestJson<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data: unknown;
  try { data = await response.json(); } catch { throw new Error(`Service returned an unreadable response (${response.status}).`); }
  if (!response.ok) {
    const error = data && typeof data === 'object' && 'error' in data ? String(data.error) : `Service refused the request (${response.status}).`;
    throw new Error(error);
  }
  return data as T;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let text = await res.text();
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === "string") text = parsed.detail;
    } catch {
      // keep raw body
    }
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

const KEY = "rag_token";

export function getToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return window.localStorage.getItem(KEY) ?? undefined;
}

export function setToken(token: string): void {
  window.localStorage.setItem(KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(KEY);
}

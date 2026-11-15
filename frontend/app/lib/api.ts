const tokenKey = "aye_api_token";

export function saveApiToken(token: string) {
  window.sessionStorage.setItem(tokenKey, token);
}

export function clearApiToken() {
  window.sessionStorage.removeItem(tokenKey);
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const token = window.sessionStorage.getItem(tokenKey);
  if (!token) throw new Error("Enter the local API token to continue.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

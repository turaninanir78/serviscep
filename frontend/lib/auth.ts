// NOT: localStorage XSS'e karsi savunmasiz (sayfada calisan herhangi bir
// script token'i okuyabilir). Panel henuz internal/test amacli oldugu icin
// simdilik kabul edilebilir; ileride httpOnly cookie'ye gecis
// degerlendirilmeli (bu, backend'de cookie-based auth destegi gerektirir -
// ayri, daha buyuk bir is).
const TOKEN_KEY = "serviscep_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

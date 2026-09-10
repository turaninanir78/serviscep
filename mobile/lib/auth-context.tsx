import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "./api";
import { clearToken, getToken, setToken } from "./storage";

interface AuthContextValue {
  isLoading: boolean;
  isAuthenticated: boolean;
  tenantName: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (tenantName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [tenantName, setTenantName] = useState<string | null>(null);

  async function refreshTenant(): Promise<void> {
    try {
      const tenant = await api.getMyTenant();
      setTenantName(tenant.name);
      setIsAuthenticated(true);
    } catch {
      setIsAuthenticated(false);
      setTenantName(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Depolanmis bir token var mi - varsa GERCEKTEN gecerli mi diye
      // /tenants/me ile dogruluyoruz (web'deki auth-guard ile ayni mantik:
      // token'in varligi tek basina yeterli degil, suresi dolmus olabilir).
      const token = await getToken();
      if (token) {
        await refreshTenant();
      }
      if (!cancelled) setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const { access_token } = await api.login(email, password);
    await setToken(access_token);
    await refreshTenant();
  }

  async function register(
    tenantNameInput: string,
    email: string,
    password: string,
  ): Promise<void> {
    const { access_token } = await api.register(tenantNameInput, email, password);
    await setToken(access_token);
    await refreshTenant();
  }

  async function logout(): Promise<void> {
    // Sunucuya bildirilecek bir sey yok (mobil'de cookie/refresh-token
    // yok) - logout tamamen istemci tarafinda, secure storage'dan silmek
    // yeterli.
    await clearToken();
    setIsAuthenticated(false);
    setTenantName(null);
  }

  return (
    <AuthContext.Provider
      value={{ isLoading, isAuthenticated, tenantName, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

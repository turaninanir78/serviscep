import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "./api";
import { clearToken, getToken, setToken } from "./storage";

// Backend'in Tenant.timezone kolonuyla ayni varsayilan (bkz.
// backend/app/models - server_default="Europe/Istanbul") - sadece
// authenticate olmadan ONCEKI kisa an icin bir baslangic degeri, gercek
// deger her zaman /tenants/me'den geliyor.
const DEFAULT_TIMEZONE = "Europe/Istanbul";

interface AuthContextValue {
  isLoading: boolean;
  isAuthenticated: boolean;
  tenantName: string | null;
  tenantTimezone: string;
  login: (emailOrPhone: string, password: string) => Promise<void>;
  // Telefon+OTP kaydinin SON adimi - ilk iki adim (kod isteme/dogrulama)
  // henuz bir hesap/oturum olusturmadigi icin auth state'i etkilemiyor,
  // ekranlar bunlari dogrudan api.requestRegisterOtp/verifyRegisterOtp ile
  // cagiriyor (bkz. app/register.tsx).
  completeRegistration: (
    registrationToken: string,
    tenantName: string,
    password: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [tenantName, setTenantName] = useState<string | null>(null);
  const [tenantTimezone, setTenantTimezone] = useState<string>(DEFAULT_TIMEZONE);

  async function refreshTenant(): Promise<void> {
    try {
      const tenant = await api.getMyTenant();
      setTenantName(tenant.name);
      setTenantTimezone(tenant.timezone);
      setIsAuthenticated(true);
    } catch {
      setIsAuthenticated(false);
      setTenantName(null);
      setTenantTimezone(DEFAULT_TIMEZONE);
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

  async function login(emailOrPhone: string, password: string): Promise<void> {
    const { access_token } = await api.login(emailOrPhone, password);
    await setToken(access_token);
    await refreshTenant();
  }

  async function completeRegistration(
    registrationToken: string,
    tenantNameInput: string,
    password: string,
  ): Promise<void> {
    const { access_token } = await api.completeRegister(
      registrationToken,
      tenantNameInput,
      password,
    );
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
    setTenantTimezone(DEFAULT_TIMEZONE);
  }

  return (
    <AuthContext.Provider
      value={{
        isLoading,
        isAuthenticated,
        tenantName,
        tenantTimezone,
        login,
        completeRegistration,
        logout,
      }}
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

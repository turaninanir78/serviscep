import type { Appointment, Customer, Service, StaffMember, Tenant } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg?: string }) => item.msg).join(", ");
    }
  } catch {
    // gövde JSON değil veya boş - genel mesaja düş
  }
  return `İstek başarısız oldu (HTTP ${res.status}).`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorMessage(res));
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  register: (tenantName: string, email: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ tenant_name: tenantName, email, password }),
    }),

  getMyTenant: (token: string) => request<Tenant>("/tenants/me", {}, token),

  getAppointments: (token: string) => request<Appointment[]>("/appointments", {}, token),

  getCustomers: (token: string) => request<Customer[]>("/customers", {}, token),

  getServices: (token: string) => request<Service[]>("/services", {}, token),

  getStaffMembers: (token: string) => request<StaffMember[]>("/staff_members", {}, token),
};

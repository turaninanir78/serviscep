import type {
  Appointment,
  AvailabilityRule,
  AvailableSlotsResponse,
  Customer,
  Service,
  StaffMember,
  Tenant,
} from "./types";

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

export interface CreateStaffMemberInput {
  name: string;
}

export interface UpdateStaffMemberInput {
  is_active?: boolean;
  name?: string;
}

export interface CreateServiceInput {
  name: string;
  duration_minutes: number;
  price?: number;
  default_buffer_minutes?: number;
}

export interface UpdateServiceInput {
  is_active?: boolean;
}

export interface CreateAvailabilityRuleInput {
  staff_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface CreateAppointmentInput {
  staff_id: number;
  service_id: number;
  customer_id: number;
  start_at: string;
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

  createAppointment: (token: string, input: CreateAppointmentInput) =>
    request<Appointment>(
      "/appointments",
      { method: "POST", body: JSON.stringify(input) },
      token,
    ),

  cancelAppointment: (token: string, id: number) =>
    request<Appointment>(`/appointments/${id}/cancel`, { method: "POST" }, token),

  getAvailableSlots: (token: string, staffId: number, serviceId: number, date: string) =>
    request<AvailableSlotsResponse>(
      `/availability/slots?staff_id=${staffId}&service_id=${serviceId}&date=${date}`,
      {},
      token,
    ),

  getCustomers: (token: string) => request<Customer[]>("/customers", {}, token),

  getServices: (token: string) => request<Service[]>("/services", {}, token),

  createService: (token: string, input: CreateServiceInput) =>
    request<Service>("/services", { method: "POST", body: JSON.stringify(input) }, token),

  updateService: (token: string, id: number, input: UpdateServiceInput) =>
    request<Service>(
      `/services/${id}`,
      { method: "PATCH", body: JSON.stringify(input) },
      token,
    ),

  getStaffMembers: (token: string) => request<StaffMember[]>("/staff_members", {}, token),

  createStaffMember: (token: string, input: CreateStaffMemberInput) =>
    request<StaffMember>(
      "/staff_members",
      { method: "POST", body: JSON.stringify(input) },
      token,
    ),

  updateStaffMember: (token: string, id: number, input: UpdateStaffMemberInput) =>
    request<StaffMember>(
      `/staff_members/${id}`,
      { method: "PATCH", body: JSON.stringify(input) },
      token,
    ),

  getAvailabilityRules: (token: string) =>
    request<AvailabilityRule[]>("/availability_rules", {}, token),

  createAvailabilityRule: (token: string, input: CreateAvailabilityRuleInput) =>
    request<AvailabilityRule>(
      "/availability_rules",
      { method: "POST", body: JSON.stringify(input) },
      token,
    ),
};

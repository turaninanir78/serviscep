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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  // Auth artik httpOnly cookie ile tasiniyor - JS'in token'i okuyup
  // Authorization header'ina eklemesi gerekmiyor (zaten okuyamaz). Tarayicinin
  // cookie'yi otomatik eklemesi icin credentials: "include" sart, cunku
  // frontend (localhost:3000) ve backend (localhost:8000) farkli origin'ler.
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorMessage(res));
  }

  // 204'un yani sira login/register de artik govdesiz donuyor (token
  // Set-Cookie header'iyla tasiniyor) - bos govdede res.json() bir
  // SyntaxError firlatirdi, bu yuzden once metni kontrol ediyoruz.
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
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

export interface RescheduleAppointmentInput {
  start_at: string;
}

export const api = {
  login: (email: string, password: string) =>
    request<void>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  register: (tenantName: string, email: string, password: string) =>
    request<void>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ tenant_name: tenantName, email, password }),
    }),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  getMyTenant: () => request<Tenant>("/tenants/me"),

  getAppointments: () => request<Appointment[]>("/appointments"),

  createAppointment: (input: CreateAppointmentInput) =>
    request<Appointment>("/appointments", { method: "POST", body: JSON.stringify(input) }),

  confirmAppointment: (id: number) =>
    request<Appointment>(`/appointments/${id}/confirm`, { method: "POST" }),

  cancelAppointment: (id: number) =>
    request<Appointment>(`/appointments/${id}/cancel`, { method: "POST" }),

  completeAppointment: (id: number) =>
    request<Appointment>(`/appointments/${id}/complete`, { method: "POST" }),

  markAppointmentNoShow: (id: number) =>
    request<Appointment>(`/appointments/${id}/no-show`, { method: "POST" }),

  rescheduleAppointment: (id: number, input: RescheduleAppointmentInput) =>
    request<Appointment>(`/appointments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  getAvailableSlots: (staffId: number, serviceId: number, date: string) =>
    request<AvailableSlotsResponse>(
      `/availability/slots?staff_id=${staffId}&service_id=${serviceId}&date=${date}`,
    ),

  getCustomers: () => request<Customer[]>("/customers"),

  getServices: () => request<Service[]>("/services"),

  createService: (input: CreateServiceInput) =>
    request<Service>("/services", { method: "POST", body: JSON.stringify(input) }),

  updateService: (id: number, input: UpdateServiceInput) =>
    request<Service>(`/services/${id}`, { method: "PATCH", body: JSON.stringify(input) }),

  getStaffMembers: () => request<StaffMember[]>("/staff_members"),

  createStaffMember: (input: CreateStaffMemberInput) =>
    request<StaffMember>("/staff_members", { method: "POST", body: JSON.stringify(input) }),

  updateStaffMember: (id: number, input: UpdateStaffMemberInput) =>
    request<StaffMember>(`/staff_members/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),

  getAvailabilityRules: () => request<AvailabilityRule[]>("/availability_rules"),

  createAvailabilityRule: (input: CreateAvailabilityRuleInput) =>
    request<AvailabilityRule>("/availability_rules", {
      method: "POST",
      body: JSON.stringify(input),
    }),
};

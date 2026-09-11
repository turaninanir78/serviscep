import { getToken } from "./storage";
import type {
  Appointment,
  AvailabilityRule,
  AvailableSlotsResponse,
  ConsentStatus,
  Customer,
  LegalDocument,
  Service,
  StaffMember,
  Tenant,
  User,
} from "./types";

// Android emulator'da "localhost" emulator'in KENDI loopback'i olur, host
// makineye ulasmak icin 10.0.2.2 gerekir - iOS simulator ve web'de ise
// localhost dogrudan calisir. Gercek cihaz/farkli ag icin
// EXPO_PUBLIC_BACKEND_URL .env ile override edilebilir (bkz. .env.example).
const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

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
    // govde JSON degil veya bos - genel mesaja dus
  }
  return `İstek başarısız oldu (HTTP ${res.status}).`;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  // Web panelinin aksine (httpOnly cookie otomatik gonderilir), mobil'de
  // token'i biz okuyup Authorization header'ina EKLEMEMIZ gerekiyor -
  // native app'lerin tarayici cookie jar'i yok.
  const token = await getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorMessage(res));
  }

  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

interface MobileTokenResponse {
  access_token: string;
  token_type: string;
}

export interface RescheduleAppointmentInput {
  start_at: string;
}

export interface CreateAppointmentInput {
  staff_id: number;
  service_id: number;
  customer_id: number;
  start_at: string;
}

export interface CreateCustomerInput {
  whatsapp_number: string;
  display_name?: string | null;
}

export interface CreateAvailabilityRuleInput {
  staff_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface UpdateAvailabilityRuleInput {
  weekday?: number;
  start_time?: string;
  end_time?: string;
}

export interface OtpRequestResponse {
  message: string;
  debug_code: string | null;
}

export const api = {
  login: (emailOrPhone: string, password: string) =>
    request<MobileTokenResponse>("/auth/mobile/login", {
      method: "POST",
      body: JSON.stringify({ email_or_phone: emailOrPhone, password }),
    }),

  // Telefon + OTP ile kayit - uc adima bolunmus (bkz. web'in
  // frontend/lib/api.ts dosyasindaki ayni fonksiyonlarin ustundeki yorum).
  // Eski tek adimli /auth/mobile/register artik UI'dan cagrilmiyor
  // (backend'de sadece geriye donuk uyumluluk icin duruyor).
  requestRegisterOtp: (countryCode: string, phoneNumber: string) =>
    request<OtpRequestResponse>("/auth/register/request-otp", {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode, phone_number: phoneNumber }),
    }),

  verifyRegisterOtp: (countryCode: string, phoneNumber: string, code: string) =>
    request<{ registration_token: string }>("/auth/register/verify-otp", {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode, phone_number: phoneNumber, code }),
    }),

  completeRegister: (
    registrationToken: string,
    tenantName: string,
    password: string,
    acceptedTerms: boolean,
  ) =>
    request<MobileTokenResponse>("/auth/mobile/register/complete", {
      method: "POST",
      body: JSON.stringify({
        registration_token: registrationToken,
        tenant_name: tenantName,
        password,
        accepted_terms: acceptedTerms,
      }),
    }),

  getMe: () => request<User>("/auth/me"),

  // KVKK sozlesme/onay - bkz. backend/app/legal.py. Gercek hukuki metin
  // YOK, content su an sadece yer tutucu.
  getLegalDocument: (type: string) => request<LegalDocument>(`/legal/${type}`),

  getConsentStatus: () => request<ConsentStatus>("/legal/consent-status"),

  acceptDocument: (documentId: number) =>
    request<void>("/legal/accept", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId }),
    }),

  requestAddEmailOtp: (email: string) =>
    request<OtpRequestResponse>("/auth/profile/request-email-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  verifyAddEmail: (email: string, code: string) =>
    request<User>("/auth/profile/verify-email", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  getMyTenant: () => request<Tenant>("/tenants/me"),

  getAppointments: () => request<Appointment[]>("/appointments"),

  getAppointment: (id: number) => request<Appointment>(`/appointments/${id}`),

  createAppointment: (input: CreateAppointmentInput) =>
    request<Appointment>("/appointments", { method: "POST", body: JSON.stringify(input) }),

  getCustomers: () => request<Customer[]>("/customers"),

  getCustomer: (id: number) => request<Customer>(`/customers/${id}`),

  createCustomer: (input: CreateCustomerInput) =>
    request<Customer>("/customers", { method: "POST", body: JSON.stringify(input) }),

  getServices: () => request<Service[]>("/services"),

  getStaffMembers: () => request<StaffMember[]>("/staff_members"),

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

  getAvailabilityRules: () => request<AvailabilityRule[]>("/availability_rules"),

  createAvailabilityRule: (input: CreateAvailabilityRuleInput) =>
    request<AvailabilityRule>("/availability_rules", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  updateAvailabilityRule: (id: number, input: UpdateAvailabilityRuleInput) =>
    request<AvailabilityRule>(`/availability_rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
};

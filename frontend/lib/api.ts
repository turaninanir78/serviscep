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

export interface OtpRequestResponse {
  message: string;
  debug_code: string | null;
}

export interface PasswordResetRequestOtpResponse {
  message: string;
  // true ise kod HENUZ gonderilmedi - kullanicidan "sms" / "email" secimi
  // isteyip AYNI istegi channel ile tekrar gondermek gerekir (bkz.
  // backend/app/api/auth.py::password_reset_request_otp).
  channel_choice_required: boolean;
  available_channels: ("sms" | "email")[];
  debug_code: string | null;
}

export const api = {
  login: (emailOrPhone: string, password: string) =>
    request<void>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email_or_phone: emailOrPhone, password }),
    }),

  // Telefon + OTP ile kayit - uc adima bolunmus (bkz.
  // backend/app/api/auth.py'deki ayni isimli endpoint'lerin ustundeki
  // yorum). Eski tek adimli /auth/register artik web UI'dan cagrilmiyor
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
    request<void>("/auth/register/complete", {
      method: "POST",
      body: JSON.stringify({
        registration_token: registrationToken,
        tenant_name: tenantName,
        password,
        accepted_terms: acceptedTerms,
      }),
    }),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  // KVKK sozlesme/onay - bkz. backend/app/legal.py. Gercek hukuki metin
  // YOK, content su an sadece yer tutucu.
  getLegalDocument: (type: string) => request<LegalDocument>(`/legal/${type}`),

  getConsentStatus: () => request<ConsentStatus>("/legal/consent-status"),

  acceptDocument: (documentId: number) =>
    request<void>("/legal/accept", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId }),
    }),

  getMe: () => request<User>("/auth/me"),

  // Ayni akis hem "ilk kez ekleme" hem "degistirme" icin kullaniliyor -
  // backend kosulsuzca uzerine yaziyor (bkz. backend/app/api/auth.py::profile_verify_email).
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

  // Telefon zorunlu alan oldugu icin sadece DEGISTIRME var, kaldirma yok.
  requestChangePhoneOtp: (countryCode: string, phoneNumber: string) =>
    request<OtpRequestResponse>("/auth/profile/request-phone-otp", {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode, phone_number: phoneNumber }),
    }),

  verifyChangePhoneOtp: (countryCode: string, phoneNumber: string, code: string) =>
    request<User>("/auth/profile/verify-phone-otp", {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode, phone_number: phoneNumber, code }),
    }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>("/auth/profile/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  // Sifremi unuttum - uc adim (bkz. backend/app/api/auth.py::password_reset_*
  // endpoint'lerinin ustundeki yorum). `channel` verilmezse: kullanicinin
  // dogrulanmis email'i yoksa otomatik SMS gonderilir, varsa kod
  // GONDERILMEDEN sadece secenekler bildirilir (channel_choice_required).
  requestPasswordResetOtp: (countryCode: string, phoneNumber: string, channel?: "sms" | "email") =>
    request<PasswordResetRequestOtpResponse>("/auth/password-reset/request-otp", {
      method: "POST",
      body: JSON.stringify({
        country_code: countryCode,
        phone_number: phoneNumber,
        ...(channel ? { channel } : {}),
      }),
    }),

  verifyPasswordResetOtp: (countryCode: string, phoneNumber: string, code: string) =>
    request<{ reset_token: string }>("/auth/password-reset/verify-otp", {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode, phone_number: phoneNumber, code }),
    }),

  completePasswordReset: (resetToken: string, newPassword: string) =>
    request<void>("/auth/password-reset/complete", {
      method: "POST",
      body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
    }),

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

  // KVKK unutulma hakki - GERI ALINAMAZ (bkz. backend/app/api/customers.py::request_customer_deletion).
  requestCustomerDeletion: (id: number) =>
    request<Customer>(`/customers/${id}/request-deletion`, { method: "POST" }),

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

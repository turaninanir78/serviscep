// Backend response semalariyla birebir eslesiyor (bkz. backend/app/schemas)
// - web'in frontend/lib/types.ts dosyasiyla ayni sekiller, ayri client.

export interface Tenant {
  id: number;
  name: string;
  timezone: string;
  // Aktif calisma baglamindaki rol - "owner" (kendi isletmesi) veya
  // "staff" (davetle baglanmis) - bkz. backend/app/security.py::AuthContext.
  // SADECE arayuzde owner'a ozel bolumleri gizlemek icin (backend zaten
  // bagimsiz olarak yetki kontrolu yapiyor).
  my_role: string;
  my_permissions: string[];
}

export interface User {
  id: number;
  tenant_id: number;
  email: string | null;
  phone: string | null;
  role: string;
}

export interface Appointment {
  id: number;
  tenant_id: number;
  customer_id: number;
  service_id: number;
  staff_id: number;
  start_at: string;
  end_at: string;
  status: string;
  created_via: string;
  buffer_minutes: number;
}

export interface Customer {
  id: number;
  tenant_id: number;
  whatsapp_number: string;
  display_name: string | null;
  first_seen_at: string;
}

export interface Service {
  id: number;
  tenant_id: number;
  name: string;
  duration_minutes: number;
  price: string | null;
  is_active: boolean;
  default_buffer_minutes: number;
}

export interface StaffMember {
  id: number;
  tenant_id: number;
  name: string;
  is_active: boolean;
}

export interface AvailableSlotsResponse {
  date: string;
  staff_id: number;
  service_id: number;
  slots: string[];
}

export interface AvailabilityRule {
  id: number;
  tenant_id: number;
  staff_id: number;
  // 0=Pazartesi ... 6=Pazar (backend'deki date.weekday() ile ayni kodlama)
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface LegalDocument {
  id: number;
  type: string;
  version: string;
  content: string;
  effective_date: string;
}

export interface ConsentStatus {
  needs_consent: boolean;
  pending_documents: LegalDocument[];
}

export interface StaffInvitation {
  id: number;
  tenant_id: number;
  phone: string;
  status: string;
  created_at: string;
  expires_at: string;
}

export interface PendingStaffInvitation {
  id: number;
  tenant_id: number;
  tenant_name: string;
  status: string;
  created_at: string;
  expires_at: string;
}

export interface StaffMembership {
  staff_member_id: number;
  role: string;
  can_view_customers: boolean;
  can_create_appointments: boolean;
  can_cancel_appointments: boolean;
  can_confirm_complete_appointments: boolean;
  can_manage_availability: boolean;
  can_manage_services: boolean;
}

export type StaffPermissionKey =
  | "can_view_customers"
  | "can_create_appointments"
  | "can_cancel_appointments"
  | "can_confirm_complete_appointments"
  | "can_manage_availability"
  | "can_manage_services";

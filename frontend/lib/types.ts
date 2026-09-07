export interface Tenant {
  id: number;
  name: string;
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

export interface AvailabilityRule {
  id: number;
  tenant_id: number;
  staff_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
}

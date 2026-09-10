import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { render } from "@testing-library/react-native";

import { api } from "@/lib/api";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";
import AppointmentsScreen from "./index";

jest.mock("@/lib/api");
jest.mock("expo-router", () => {
  const { useEffect } = require("react");
  return {
    router: { push: jest.fn(), replace: jest.fn() },
    // Test ortaminda gercek bir navigation/focus context yok - useFocusEffect'i
    // adi useEffect gibi (bir kere, mount'ta) calisacak sekilde sadelestiriyoruz.
    useFocusEffect: (effect: () => void) => {
      useEffect(() => {
        effect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
    },
  };
});

const mockedApi = api as jest.Mocked<typeof api>;

// Bu dosyanin ilk testi NavRow/StatusBadge dahil bircok modulun SOGUK
// Babel transform'unu tetikliyor - varsayilan 5s zaman asimi bazen yetmiyor.
jest.setTimeout(15000);

const staffMembers: StaffMember[] = [
  { id: 1, tenant_id: 10, name: "Zeynep Usta", is_active: true },
];
const services: Service[] = [
  {
    id: 2,
    tenant_id: 10,
    name: "Saç Kesimi",
    duration_minutes: 30,
    price: null,
    is_active: true,
    default_buffer_minutes: 0,
  },
];
const customers: Customer[] = [
  {
    id: 3,
    tenant_id: 10,
    whatsapp_number: "905551112233",
    display_name: "Elif Demir",
    first_seen_at: "2026-01-01T00:00:00Z",
  },
];
const appointments: Appointment[] = [
  {
    id: 100,
    tenant_id: 10,
    customer_id: 3,
    service_id: 2,
    staff_id: 1,
    start_at: "2026-09-14T09:00:00+03:00",
    end_at: "2026-09-14T09:30:00+03:00",
    status: "pending",
    created_via: "dashboard",
    buffer_minutes: 0,
  },
];

describe("AppointmentsScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("randevu listesi müşteri/hizmet/personel adlarıyla ve durum rozetiyle gösterilir", async () => {
    mockedApi.getAppointments.mockResolvedValue(appointments);
    mockedApi.getCustomers.mockResolvedValue(customers);
    mockedApi.getServices.mockResolvedValue(services);
    mockedApi.getStaffMembers.mockResolvedValue(staffMembers);

    const { findByText, getByText } = render(<AppointmentsScreen />);

    expect(await findByText("Elif Demir")).toBeTruthy();
    expect(getByText(/Saç Kesimi/)).toBeTruthy();
    expect(getByText("Beklemede")).toBeTruthy();
  });

  test("boş listede uygun mesaj gösterilir", async () => {
    mockedApi.getAppointments.mockResolvedValue([]);
    mockedApi.getCustomers.mockResolvedValue([]);
    mockedApi.getServices.mockResolvedValue([]);
    mockedApi.getStaffMembers.mockResolvedValue([]);

    const { findByText } = render(<AppointmentsScreen />);
    expect(await findByText("Henüz randevu yok.")).toBeTruthy();
  });

  test("API hatası durumunda kullanıcıya uygun mesaj gösterilir, liste gösterilmez", async () => {
    mockedApi.getAppointments.mockRejectedValue(new Error("network fail"));
    mockedApi.getCustomers.mockResolvedValue([]);
    mockedApi.getServices.mockResolvedValue([]);
    mockedApi.getStaffMembers.mockResolvedValue([]);

    const { findByText, queryByText } = render(<AppointmentsScreen />);
    expect(await findByText("Bir şeyler ters gitti, tekrar deneyin.")).toBeTruthy();
    expect(queryByText("Henüz randevu yok.")).toBeNull();
  });
});

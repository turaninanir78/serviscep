import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";

import { api } from "@/lib/api";
import type { Customer, Service, StaffMember } from "@/lib/types";
import NewAppointmentScreen from "./new";

jest.mock("@/lib/api");
// router'i disaridan bir degiskenle factory'ye tasimiyoruz (jest.mock
// hoisting'i yuzunden bu modulu tetikleyen ilk import, o degisken henuz
// atanmadan calisabilir ve router "undefined" kalir) - bunun yerine
// factory kendi icinde olusturuyor, testte de ayni mock nesneye normal
// bir import ile erisiyoruz (bkz. asagidaki "import { router }").
jest.mock("expo-router", () => {
  const { useEffect } = require("react");
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    // AppointmentsScreen testindekiyle ayni sadelestirme: gercek bir
    // navigation/focus context yok, mount'ta bir kere calissin yeterli.
    useFocusEffect: (effect: () => void) => {
      useEffect(() => {
        effect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
    },
  };
});

const mockedApi = api as jest.Mocked<typeof api>;
const mockRouter = router as jest.Mocked<typeof router>;

jest.setTimeout(15000);

const staffMembers: StaffMember[] = [
  { id: 1, tenant_id: 10, name: "Zeynep Usta", is_active: true },
  { id: 2, tenant_id: 10, name: "Pasif Usta", is_active: false },
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

function setupDefaultMocks() {
  mockedApi.getStaffMembers.mockResolvedValue(staffMembers);
  mockedApi.getServices.mockResolvedValue(services);
  mockedApi.getCustomers.mockResolvedValue(customers);
}

describe("NewAppointmentScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultMocks();
  });

  test("personel ve hizmet seçilince o an seçili tarih için müsait slotlar yüklenir", async () => {
    mockedApi.getAvailableSlots.mockResolvedValue({
      date: "2026-09-10",
      staff_id: 1,
      service_id: 2,
      slots: ["2026-09-10T09:00:00+03:00"],
    });

    const { findByTestId, getByText } = render(<NewAppointmentScreen />);

    fireEvent.press(await findByTestId("staff-option-1"));
    fireEvent.press(await findByTestId("service-option-2"));

    await waitFor(() => expect(mockedApi.getAvailableSlots).toHaveBeenCalledWith(1, 2, expect.any(String)));
    expect(getByText(/09:00/)).toBeTruthy();

    // Pasif personel secilebilir listede hic gorunmemeli.
    expect(() => getByText("Pasif Usta")).toThrow();
  });

  test("slot ve müşteri seçilip kaydedince doğru randevu isteği yapılır ve geri dönülür", async () => {
    mockedApi.getAvailableSlots.mockResolvedValue({
      date: "2026-09-10",
      staff_id: 1,
      service_id: 2,
      slots: ["2026-09-10T09:00:00+03:00"],
    });
    mockedApi.createAppointment.mockResolvedValue({
      id: 99,
      tenant_id: 10,
      customer_id: 3,
      service_id: 2,
      staff_id: 1,
      start_at: "2026-09-10T09:00:00+03:00",
      end_at: "2026-09-10T09:30:00+03:00",
      status: "pending",
      created_via: "dashboard",
      buffer_minutes: 0,
    });

    const { findByTestId } = render(<NewAppointmentScreen />);

    fireEvent.press(await findByTestId("staff-option-1"));
    fireEvent.press(await findByTestId("service-option-2"));
    fireEvent.press(await findByTestId("slot-chip-2026-09-10T09:00:00+03:00"));
    fireEvent.changeText(await findByTestId("customer-search-input"), "Elif");
    fireEvent.press(await findByTestId("customer-option-3"));

    const submitButton = await findByTestId("new-appointment-submit");
    fireEvent.press(submitButton);

    await waitFor(() =>
      expect(mockedApi.createAppointment).toHaveBeenCalledWith({
        staff_id: 1,
        service_id: 2,
        customer_id: 3,
        start_at: "2026-09-10T09:00:00+03:00",
      }),
    );
    await waitFor(() => expect(mockRouter.back).toHaveBeenCalledTimes(1));
  });

  test("yeni müşteri ekle ile hızlıca müşteri oluşturulup seçilir", async () => {
    mockedApi.getAvailableSlots.mockResolvedValue({
      date: "2026-09-10",
      staff_id: 1,
      service_id: 2,
      slots: ["2026-09-10T09:00:00+03:00"],
    });
    mockedApi.createCustomer.mockResolvedValue({
      id: 42,
      tenant_id: 10,
      whatsapp_number: "905559998877",
      display_name: "Yeni Müşteri",
      first_seen_at: "2026-09-10T00:00:00Z",
    });

    const { findByTestId, getByText } = render(<NewAppointmentScreen />);

    fireEvent.press(await findByTestId("staff-option-1"));
    fireEvent.press(await findByTestId("service-option-2"));
    fireEvent.press(await findByTestId("slot-chip-2026-09-10T09:00:00+03:00"));

    fireEvent.press(await findByTestId("new-customer-toggle"));
    fireEvent.changeText(await findByTestId("new-customer-name"), "Yeni Müşteri");
    fireEvent.changeText(await findByTestId("new-customer-phone"), "905559998877");
    fireEvent.press(await findByTestId("new-customer-submit"));

    await waitFor(() =>
      expect(mockedApi.createCustomer).toHaveBeenCalledWith({
        whatsapp_number: "905559998877",
        display_name: "Yeni Müşteri",
      }),
    );
    expect(await findByTestId("new-appointment-submit")).toBeTruthy();
    expect(getByText("Yeni Müşteri")).toBeTruthy();
  });
});

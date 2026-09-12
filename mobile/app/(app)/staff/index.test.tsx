import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { api, ApiError } from "@/lib/api";
import type { StaffMember } from "@/lib/types";
import StaffScreen from "./index";

// Duz `jest.mock("@/lib/api")` (factory'siz) ApiError'i de otomatik
// mock'luyor - constructor govdesi calismadigi icin `.status` hic
// atanmiyor, bu da component'teki `err instanceof ApiError && err.status
// === 404` kontrolunu sessizce kirar. Gercek ApiError'i (constructor'i
// dahil) korumak icin `api` objesinin SADECE metotlarini mock'luyoruz.
jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api") as typeof import("@/lib/api");
  const mockedMethods = Object.fromEntries(
    Object.keys(actual.api).map((key) => [key, jest.fn()]),
  );
  return { ...actual, api: mockedMethods };
});
jest.mock("expo-router", () => {
  const { useEffect } = require("react");
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    useFocusEffect: (effect: () => void) => {
      useEffect(() => {
        effect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
    },
  };
});

// CI'da (yerelden daha yavas/paylasimli runner) FlatList + Modal iceren bu
// ekranin varsayilan 5000ms Jest timeout'unu asabilmesi - bkz.
// availability/index.test.tsx'teki ayni onlem.
jest.setTimeout(15000);

const mockUseAuth = jest.fn();
jest.mock("@/lib/auth-context", () => ({
  useAuth: () => mockUseAuth(),
}));

const mockedApi = api as jest.Mocked<typeof api>;

const baseStaffMember: StaffMember = { id: 1, tenant_id: 10, name: "Ben", is_active: true };

describe("StaffScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({ tenantRole: "owner" });
    mockedApi.getStaffMembers.mockResolvedValue([baseStaffMember]);
    mockedApi.getSentStaffInvitations.mockResolvedValue([]);
  });

  test("owner telefon ile personel davet edebilir", async () => {
    const invite = mockedApi.inviteStaffMember.mockResolvedValue({
      id: 5,
      tenant_id: 10,
      phone: "+905321234567",
      status: "pending",
      created_at: "2026-01-01T00:00:00Z",
      expires_at: "2026-01-08T00:00:00Z",
    });

    const { findByTestId } = render(<StaffScreen />);

    fireEvent.changeText(await findByTestId("staff-invite-phone"), "5321234567");
    fireEvent.press(await findByTestId("staff-invite-submit"));

    await waitFor(() => expect(invite).toHaveBeenCalledWith("+90", "5321234567"));
  });

  test("davetle eklenmiş personel için yetki switch'leri açılıp kapanabilir", async () => {
    mockedApi.getStaffMembership.mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: false,
      can_create_appointments: false,
      can_cancel_appointments: false,
      can_confirm_complete_appointments: false,
      can_manage_availability: false,
      can_manage_services: false,
    });
    const updatePermissions = mockedApi.updateStaffPermissions.mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: true,
      can_create_appointments: false,
      can_cancel_appointments: false,
      can_confirm_complete_appointments: false,
      can_manage_availability: false,
      can_manage_services: false,
    });

    const { findByTestId } = render(<StaffScreen />);

    fireEvent.press(await findByTestId("staff-permissions-1"));
    const toggle = await findByTestId("staff-permission-can_view_customers");
    fireEvent(toggle, "valueChange", true);

    await waitFor(() =>
      expect(updatePermissions).toHaveBeenCalledWith(1, { can_view_customers: true }),
    );
  });

  test("yerel (davetsiz) personel için 'yerel kayıt' mesajı gösterilir", async () => {
    mockedApi.getStaffMembership.mockRejectedValue(new ApiError(404, "Not found"));

    const { findByTestId, findByText } = render(<StaffScreen />);

    fireEvent.press(await findByTestId("staff-permissions-1"));

    expect(await findByText(/davetle eklenmemiş/)).toBeTruthy();
  });

  test("staff rolündeki kullanıcı davet formunu ve Yetkiler butonunu görmez", async () => {
    mockUseAuth.mockReturnValue({ tenantRole: "staff" });

    const { queryByTestId, findByText } = render(<StaffScreen />);

    await findByText("Ben");

    expect(queryByTestId("staff-invite-phone")).toBeNull();
    expect(queryByTestId("staff-permissions-1")).toBeNull();
    expect(mockedApi.getSentStaffInvitations).not.toHaveBeenCalled();
  });

  test("İşten Çıkar üyeliği sonlandırıp listeyi yeniler", async () => {
    mockedApi.getStaffMembership.mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: true,
      can_create_appointments: true,
      can_cancel_appointments: true,
      can_confirm_complete_appointments: true,
      can_manage_availability: true,
      can_manage_services: true,
    });
    const endMembership = mockedApi.endStaffMembership.mockResolvedValue({
      ...baseStaffMember,
      is_active: false,
    });

    const { findByTestId } = render(<StaffScreen />);

    fireEvent.press(await findByTestId("staff-permissions-1"));
    fireEvent.press(await findByTestId("staff-end-membership"));

    await waitFor(() => expect(endMembership).toHaveBeenCalledWith(1));
    await waitFor(() => expect(mockedApi.getStaffMembers).toHaveBeenCalledTimes(2));
  });
});

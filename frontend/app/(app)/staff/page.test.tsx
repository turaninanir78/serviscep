import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import StaffPage from "./page";

const baseStaffMember = { id: 1, tenant_id: 1, name: "Ben", is_active: true };

describe("StaffPage", () => {
  beforeEach(() => {
    // Testlerin çoğu owner görünümünü varsayıyor - sadece rol testi bunu
    // ayrıca "staff" olarak mock'luyor (bkz. aşağıdaki test).
    vi.spyOn(api, "getMyTenant").mockResolvedValue({
      id: 1,
      name: "Test İşletmesi",
      timezone: "Europe/Istanbul",
      my_role: "owner",
      my_permissions: [],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("telefon ile personel davet edilebilir ve gönderilen davetler listelenir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getStaffMembers").mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);
    const invite = vi.spyOn(api, "inviteStaffMember").mockResolvedValue({
      id: 5,
      tenant_id: 1,
      phone: "+905321234567",
      status: "pending",
      created_at: "2026-01-01T00:00:00Z",
      expires_at: "2026-01-08T00:00:00Z",
    });

    render(<StaffPage />);

    await screen.findByText("Ben");

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Davet Gönder" }));

    await waitFor(() => expect(invite).toHaveBeenCalledWith("+90", "5321234567"));
  });

  test("davetle eklenmiş personel için yetki toggle'ları görünür ve açılıp kapanabilir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getStaffMembers").mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);
    vi.spyOn(api, "getStaffMembership").mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: false,
      can_create_appointments: false,
      can_cancel_appointments: false,
      can_confirm_complete_appointments: false,
      can_manage_availability: false,
      can_manage_services: false,
    });
    const updatePermissions = vi.spyOn(api, "updateStaffPermissions").mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: true,
      can_create_appointments: false,
      can_cancel_appointments: false,
      can_confirm_complete_appointments: false,
      can_manage_availability: false,
      can_manage_services: false,
    });

    render(<StaffPage />);

    await user.click(await screen.findByRole("button", { name: "Yetkiler" }));

    const checkbox = await screen.findByRole("checkbox", { name: "Müşterileri Görüntüleme" });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);

    await waitFor(() =>
      expect(updatePermissions).toHaveBeenCalledWith(1, { can_view_customers: true }),
    );
  });

  test("yerel (davetsiz) personel için yetki paneli 'yerel kayıt' mesajı gösterir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getStaffMembers").mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);
    vi.spyOn(api, "getStaffMembership").mockRejectedValue(new ApiError(404, "Not found"));

    render(<StaffPage />);

    await user.click(await screen.findByRole("button", { name: "Yetkiler" }));

    expect(await screen.findByText(/davetle eklenmemiş/)).toBeInTheDocument();
    expect(screen.queryByText("Tüm Yetkileri Ver")).not.toBeInTheDocument();
  });

  test("Tüm Yetkileri Ver butonu tüm izinleri açık gönderir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getStaffMembers").mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);
    vi.spyOn(api, "getStaffMembership").mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: false,
      can_create_appointments: false,
      can_cancel_appointments: false,
      can_confirm_complete_appointments: false,
      can_manage_availability: false,
      can_manage_services: false,
    });
    const updatePermissions = vi.spyOn(api, "updateStaffPermissions").mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: true,
      can_create_appointments: true,
      can_cancel_appointments: true,
      can_confirm_complete_appointments: true,
      can_manage_availability: true,
      can_manage_services: true,
    });

    render(<StaffPage />);

    await user.click(await screen.findByRole("button", { name: "Yetkiler" }));
    await user.click(await screen.findByRole("button", { name: "Tüm Yetkileri Ver" }));

    await waitFor(() =>
      expect(updatePermissions).toHaveBeenCalledWith(1, {
        can_view_customers: true,
        can_create_appointments: true,
        can_cancel_appointments: true,
        can_confirm_complete_appointments: true,
        can_manage_availability: true,
        can_manage_services: true,
      }),
    );
  });

  test("İşten Çıkar, uyeligi sonlandirip listeyi yeniler", async () => {
    const user = userEvent.setup();
    const getStaffMembers = vi
      .spyOn(api, "getStaffMembers")
      .mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);
    vi.spyOn(api, "getStaffMembership").mockResolvedValue({
      staff_member_id: 1,
      role: "staff",
      can_view_customers: true,
      can_create_appointments: true,
      can_cancel_appointments: true,
      can_confirm_complete_appointments: true,
      can_manage_availability: true,
      can_manage_services: true,
    });
    const endMembership = vi
      .spyOn(api, "endStaffMembership")
      .mockResolvedValue({ ...baseStaffMember, is_active: false });

    render(<StaffPage />);

    await user.click(await screen.findByRole("button", { name: "Yetkiler" }));
    await user.click(await screen.findByRole("button", { name: "İşten Çıkar" }));

    await waitFor(() => expect(endMembership).toHaveBeenCalledWith(1));
    await waitFor(() => expect(getStaffMembers).toHaveBeenCalledTimes(2));
  });

  test("staff rolündeki kullanıcı personel ekleme/davet/düzenleme bölümlerini görmez", async () => {
    vi.spyOn(api, "getMyTenant").mockResolvedValue({
      id: 1,
      name: "Test İşletmesi",
      timezone: "Europe/Istanbul",
      my_role: "staff",
      my_permissions: ["can_view_customers"],
    });
    vi.spyOn(api, "getStaffMembers").mockResolvedValue([baseStaffMember]);
    vi.spyOn(api, "getSentStaffInvitations").mockResolvedValue([]);

    render(<StaffPage />);

    await screen.findByText("Ben");

    expect(screen.queryByText("Yerel Personel Ekle")).not.toBeInTheDocument();
    expect(screen.queryByText("Telefon ile Personel Davet Et")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yetkiler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pasif Yap" })).not.toBeInTheDocument();
  });
});

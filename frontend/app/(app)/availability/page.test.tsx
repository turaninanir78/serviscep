import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api } from "@/lib/api";
import type { StaffMember, Tenant } from "@/lib/types";
import AvailabilityPage from "./page";

const staffMembers: StaffMember[] = [{ id: 1, tenant_id: 1, name: "Ben", is_active: true }];

const ownerTenant: Tenant = {
  id: 1,
  name: "Test İşletmesi",
  timezone: "Europe/Istanbul",
  my_role: "owner",
  my_permissions: [],
  my_staff_member_id: null,
  max_advance_booking_days: null,
};

describe("AvailabilityPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "getStaffMembers").mockResolvedValue(staffMembers);
    vi.spyOn(api, "getAvailabilityRules").mockResolvedValue([]);
    vi.spyOn(api, "getAvailabilityOverrides").mockResolvedValue([]);
    vi.spyOn(api, "getMyTenant").mockResolvedValue(ownerTenant);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("standart mod seçilince süre/boşluk alanları görünür ve doğru gönderilir", async () => {
    const user = userEvent.setup();
    const createRule = vi.spyOn(api, "createAvailabilityRule").mockResolvedValue({
      id: 1,
      tenant_id: 1,
      staff_id: 1,
      weekday: 0,
      start_time: "09:00:00",
      end_time: "12:00:00",
      mode: "standard",
      slot_duration_minutes: 60,
      gap_minutes: 10,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Ben");

    // Sayfada iki "Başlangıç"/"Bitiş" alanı var (haftalık plan + istisna) -
    // ilk grup haftalık plan formuna ait.
    await user.type(screen.getAllByLabelText("Başlangıç")[0], "09:00");
    await user.type(screen.getAllByLabelText("Bitiş")[0], "12:00");
    // İki mod seçici var (haftalık plan + istisna formu) - ilki bu teste ait.
    await user.click(screen.getAllByText("Standart (sabit randevu izgarası)")[0]);

    const durationInput = screen.getAllByLabelText("Randevu Süresi (dk)")[0];
    await user.clear(durationInput);
    await user.type(durationInput, "60");
    const gapInput = screen.getAllByLabelText("Aradaki Boşluk (dk)")[0];
    await user.clear(gapInput);
    await user.type(gapInput, "10");

    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(createRule).toHaveBeenCalledWith({
        staff_id: 1,
        weekday: 0,
        start_time: "09:00",
        end_time: "12:00",
        mode: "standard",
        slot_duration_minutes: 60,
        gap_minutes: 10,
      }),
    );
  });

  test("tarihe özel istisna 'sadece bu tarih' seçeneğiyle apply_to_weekly_template=false gönderir", async () => {
    const user = userEvent.setup();
    const createOverride = vi.spyOn(api, "createAvailabilityOverride").mockResolvedValue({
      id: 1,
      tenant_id: 1,
      staff_id: 1,
      date: "2026-11-02",
      start_time: "14:00:00",
      end_time: "16:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Tarihe Özel Değişiklik");

    await user.type(screen.getByLabelText("Tarih"), "2026-11-02");
    // Sayfada iki "Başlangıç"/"Bitiş" alanı var (haftalık plan + istisna) -
    // ikinci grup istisna formuna ait.
    await user.type(screen.getAllByLabelText("Başlangıç")[1], "14:00");
    await user.type(screen.getAllByLabelText("Bitiş")[1], "16:00");

    await user.click(screen.getByRole("button", { name: "Sadece Bu Tarih İçin Kaydet" }));

    await waitFor(() =>
      expect(createOverride).toHaveBeenCalledWith(
        expect.objectContaining({
          staff_id: 1,
          date: "2026-11-02",
          start_time: "14:00",
          end_time: "16:00",
          apply_to_weekly_template: false,
        }),
      ),
    );
  });

  test("'Kalıcı Yap' butonu apply_to_weekly_template=true gönderir", async () => {
    const user = userEvent.setup();
    const createOverride = vi.spyOn(api, "createAvailabilityOverride").mockResolvedValue({
      id: 1,
      tenant_id: 1,
      staff_id: 1,
      date: "2026-11-02",
      start_time: "14:00:00",
      end_time: "16:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Tarihe Özel Değişiklik");

    await user.type(screen.getByLabelText("Tarih"), "2026-11-02");
    await user.type(screen.getAllByLabelText("Başlangıç")[1], "14:00");
    await user.type(screen.getAllByLabelText("Bitiş")[1], "16:00");

    await user.click(
      screen.getByRole("button", { name: "Kalıcı Yap (Bu Günü Her Hafta Böyle Yap)" }),
    );

    await waitFor(() =>
      expect(createOverride).toHaveBeenCalledWith(
        expect.objectContaining({ apply_to_weekly_template: true }),
      ),
    );
  });

  test("randevu açık kalma süresi kaydedilebilir", async () => {
    const user = userEvent.setup();
    const updateSettings = vi.spyOn(api, "updateBookingSettings").mockResolvedValue({
      ...ownerTenant,
      max_advance_booking_days: 7,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Randevu Açık Kalma Süresi");

    await user.click(screen.getByLabelText("Sınırsız"));
    const daysInput = await screen.findByRole("spinbutton");
    await user.clear(daysInput);
    await user.type(daysInput, "7");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith(7));
  });

  test("staff rolündeki kullanıcı randevu açık kalma süresi bölümünü görmez ve kendi planına kilitlenir", async () => {
    vi.spyOn(api, "getMyTenant").mockResolvedValue({
      ...ownerTenant,
      my_role: "staff",
      my_staff_member_id: 1,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Kendi çalışma planınız");

    expect(screen.queryByText("Randevu Açık Kalma Süresi")).not.toBeInTheDocument();
  });
});

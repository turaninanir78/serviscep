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

  test("varsayılan sekme Çalışma Saatleri'dir, mod seçimi/gelişmiş alanlar görünmez", async () => {
    render(<AvailabilityPage />);
    await screen.findByText("Ben");

    // Basit sekmede sadece Gün/Başlangıç/Bitiş var - mod ve gelismis
    // bolumlerin hicbiri gorunmemeli.
    expect(screen.queryByText("Esnek (Önerilen)")).not.toBeInTheDocument();
    expect(screen.queryByText("Standart")).not.toBeInTheDocument();
    expect(screen.queryByText("Randevu Süresi Modu")).not.toBeInTheDocument();
    expect(screen.queryByText("Özel Günler")).not.toBeInTheDocument();
    expect(screen.queryByText("Randevu Alma Süresi")).not.toBeInTheDocument();
    // Ama temel alanlar hala var.
    expect(screen.getByLabelText("Gün")).toBeInTheDocument();
    expect(screen.getByLabelText("Başlangıç")).toBeInTheDocument();
    expect(screen.getByLabelText("Bitiş")).toBeInTheDocument();
  });

  test("Gelişmiş Ayarlar'a geçince üç alt bölüm de (mod, özel günler, randevu alma süresi) görünür", async () => {
    const user = userEvent.setup();
    render(<AvailabilityPage />);
    await screen.findByText("Ben");

    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));

    expect(await screen.findByText("Randevu Süresi Modu")).toBeInTheDocument();
    expect(screen.getByText("Özel Günler")).toBeInTheDocument();
    expect(screen.getByText("Randevu Alma Süresi")).toBeInTheDocument();
    // İki ModeFields örneği var (haftalık plan + özel günler formu).
    expect(screen.getAllByText("Esnek (Önerilen)").length).toBe(2);
  });

  test("Basit sekmedeki formla oluşturulan kural her zaman esnek mod ile gönderilir", async () => {
    const user = userEvent.setup();
    const createRule = vi.spyOn(api, "createAvailabilityRule").mockResolvedValue({
      id: 1,
      tenant_id: 1,
      staff_id: 1,
      weekday: 0,
      start_time: "09:00:00",
      end_time: "18:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Ben");

    await user.type(screen.getByLabelText("Başlangıç"), "09:00");
    await user.type(screen.getByLabelText("Bitiş"), "18:00");
    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(createRule).toHaveBeenCalledWith({
        staff_id: 1,
        weekday: 0,
        start_time: "09:00",
        end_time: "18:00",
        mode: "flexible",
        slot_duration_minutes: null,
        gap_minutes: 0,
      }),
    );
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
    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));
    await screen.findByText("Randevu Süresi Modu");

    // Gelismis sekmede iki "Başlangıç"/"Bitiş" alanı var (haftalık plan
    // formu + özel günler formu) - ilk grup haftalık plan formuna ait.
    await user.type(screen.getAllByLabelText("Başlangıç")[0], "09:00");
    await user.type(screen.getAllByLabelText("Bitiş")[0], "12:00");
    // İki mod seçici var (haftalık plan + özel günler formu) - ilki bu teste ait.
    await user.click(screen.getAllByText("Standart")[0]);

    const durationInput = screen.getAllByLabelText("Randevu Süresi (dk)")[0];
    await user.clear(durationInput);
    await user.type(durationInput, "60");
    const gapInput = screen.getAllByLabelText("Aradaki Boşluk (dk)")[0];
    await user.clear(gapInput);
    await user.type(gapInput, "10");

    await user.click(screen.getAllByRole("button", { name: "Ekle" })[0]);

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
    await screen.findByText("Ben");
    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));
    await screen.findByText("Özel Günler");

    await user.type(screen.getByLabelText("Tarih"), "2026-11-02");
    // İkinci grup ("Başlangıç"/"Bitiş") özel gunler formuna ait.
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
    await screen.findByText("Ben");
    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));
    await screen.findByText("Özel Günler");

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
    await screen.findByText("Ben");
    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));
    await screen.findByText("Randevu Alma Süresi");

    await user.click(screen.getByLabelText("Sınırsız"));
    const daysInput = await screen.findByRole("spinbutton");
    await user.clear(daysInput);
    await user.type(daysInput, "7");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith(7));
  });

  test("staff rolündeki kullanıcı Gelişmiş Ayarlar'da randevu alma süresi bölümünü görmez ve kendi planına kilitlenir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMyTenant").mockResolvedValue({
      ...ownerTenant,
      my_role: "staff",
      my_staff_member_id: 1,
    });

    render(<AvailabilityPage />);
    await screen.findByText("Kendi çalışma planınız");

    await user.click(screen.getByRole("button", { name: "Gelişmiş Ayarlar" }));
    await screen.findByText("Özel Günler");

    expect(screen.queryByText("Randevu Alma Süresi")).not.toBeInTheDocument();
  });
});

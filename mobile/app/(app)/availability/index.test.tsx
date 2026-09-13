import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { api } from "@/lib/api";
import type { AvailabilityOverride, AvailabilityRule, StaffMember, Tenant } from "@/lib/types";
import AvailabilityScreen from "./index";

jest.mock("@/lib/api");
// Diger ekran testlerindeki (appointments/new.test.tsx) ayni sebep: router
// nesnesini disaridan bir degiskenle factory'ye tasimiyoruz - jest.mock
// hoisting'i yuzunden bu ekranin importu, o degisken henuz atanmadan
// tetiklenebilir. NavRow bu ekranda render edildigi icin router burada da
// mocklanmis olmali, ama testlerde router cagrisi ayrica doğrulanmıyor.
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

const mockedApi = api as jest.Mocked<typeof api>;

jest.setTimeout(15000);

const ownerTenant: Tenant = {
  id: 10,
  name: "Test İşletmesi",
  timezone: "Europe/Istanbul",
  my_role: "owner",
  my_permissions: [],
  my_staff_member_id: null,
  max_advance_booking_days: null,
};

const staffMembers: StaffMember[] = [
  { id: 1, tenant_id: 10, name: "Elif Usta", is_active: true },
  { id: 2, tenant_id: 10, name: "Zeynep Usta", is_active: true },
];
const rules: AvailabilityRule[] = [
  {
    id: 100,
    tenant_id: 10,
    staff_id: 1,
    weekday: 0,
    start_time: "09:00:00",
    end_time: "18:00:00",
    mode: "flexible",
    slot_duration_minutes: null,
    gap_minutes: 0,
  },
  {
    id: 101,
    tenant_id: 10,
    staff_id: 2,
    weekday: 2,
    start_time: "10:00:00",
    end_time: "16:00:00",
    mode: "flexible",
    slot_duration_minutes: null,
    gap_minutes: 0,
  },
];

function setupDefaultMocks() {
  mockedApi.getStaffMembers.mockResolvedValue(staffMembers);
  mockedApi.getAvailabilityRules.mockResolvedValue(rules);
  mockedApi.getAvailabilityOverrides.mockResolvedValue([]);
  mockedApi.getMyTenant.mockResolvedValue(ownerTenant);
}

describe("AvailabilityScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultMocks();
  });

  test("ilk personelin kuralları gösterilir, diğer personelin kuralı görünmez", async () => {
    const { findByText, queryByText } = render(<AvailabilityScreen />);

    expect(await findByText(/Pazartesi 09:00–18:00/)).toBeTruthy();
    // Zeynep Usta'nin kurali (staff_id=2), varsayilan secili personel
    // (Elif Usta, staff_id=1) icin gorunmemeli.
    expect(queryByText(/Çarşamba 10:00–16:00/)).toBeNull();
  });

  test("başka personel seçilince o personelin kuralları gösterilir", async () => {
    const { findByTestId, findByText, queryByText } = render(<AvailabilityScreen />);

    await findByText(/Pazartesi 09:00–18:00/);
    fireEvent.press(await findByTestId("staff-filter-2"));

    expect(await findByText(/Çarşamba 10:00–16:00/)).toBeTruthy();
    expect(queryByText(/Pazartesi 09:00–18:00/)).toBeNull();
  });

  test("gün ve saat girilip Ekle'ye basınca doğru API çağrısı yapılır (esnek mod varsayılan)", async () => {
    mockedApi.createAvailabilityRule.mockResolvedValue({
      id: 200,
      tenant_id: 10,
      staff_id: 1,
      weekday: 1,
      start_time: "11:00:00",
      end_time: "15:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    const { findByTestId } = render(<AvailabilityScreen />);
    await findByTestId("weekday-chip-0");

    fireEvent.press(await findByTestId("weekday-chip-1"));
    fireEvent.changeText(await findByTestId("start-time-input"), "11:00");
    fireEvent.changeText(await findByTestId("end-time-input"), "15:00");
    fireEvent.press(await findByTestId("add-rule-submit"));

    await waitFor(() =>
      expect(mockedApi.createAvailabilityRule).toHaveBeenCalledWith({
        staff_id: 1,
        weekday: 1,
        start_time: "11:00",
        end_time: "15:00",
        mode: "flexible",
        slot_duration_minutes: null,
        gap_minutes: 0,
      }),
    );
  });

  test("standart mod seçilince süre/boşluk alanları görünür ve doğru gönderilir", async () => {
    mockedApi.createAvailabilityRule.mockResolvedValue({
      id: 201,
      tenant_id: 10,
      staff_id: 1,
      weekday: 0,
      start_time: "09:00:00",
      end_time: "12:00:00",
      mode: "standard",
      slot_duration_minutes: 60,
      gap_minutes: 10,
    });

    const { findByTestId } = render(<AvailabilityScreen />);
    await findByTestId("weekday-chip-0");

    fireEvent.changeText(await findByTestId("start-time-input"), "09:00");
    fireEvent.changeText(await findByTestId("end-time-input"), "12:00");
    fireEvent.press(await findByTestId("rule-mode-standard"));
    fireEvent.changeText(await findByTestId("rule-slot-duration"), "60");
    fireEvent.changeText(await findByTestId("rule-gap-minutes"), "10");
    fireEvent.press(await findByTestId("add-rule-submit"));

    await waitFor(() =>
      expect(mockedApi.createAvailabilityRule).toHaveBeenCalledWith({
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

  test("bitiş saati başlangıçtan önceyse hata gösterilir, API çağrılmaz", async () => {
    const { findByTestId, findByText } = render(<AvailabilityScreen />);
    await findByTestId("weekday-chip-0");

    fireEvent.changeText(await findByTestId("start-time-input"), "18:00");
    fireEvent.changeText(await findByTestId("end-time-input"), "09:00");
    fireEvent.press(await findByTestId("add-rule-submit"));

    expect(await findByText("Bitiş saati başlangıç saatinden sonra olmalı.")).toBeTruthy();
    expect(mockedApi.createAvailabilityRule).not.toHaveBeenCalled();
  });

  test("tarihe özel istisna 'sadece bu tarih' ile apply_to_weekly_template=false gönderir", async () => {
    const createOverride = mockedApi.createAvailabilityOverride.mockResolvedValue({
      id: 300,
      tenant_id: 10,
      staff_id: 1,
      date: "2026-11-02",
      start_time: "14:00:00",
      end_time: "16:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    const { findByTestId } = render(<AvailabilityScreen />);
    await findByTestId("override-date-input");

    fireEvent.changeText(await findByTestId("override-date-input"), "2026-11-02");
    fireEvent.changeText(await findByTestId("override-start-input"), "14:00");
    fireEvent.changeText(await findByTestId("override-end-input"), "16:00");
    fireEvent.press(await findByTestId("override-save-once"));

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

  test("'Kalıcı Yap' butonu apply_to_weekly_template=true gönderir ve liste yenilenir", async () => {
    const createOverride = mockedApi.createAvailabilityOverride.mockResolvedValue({
      id: 301,
      tenant_id: 10,
      staff_id: 1,
      date: "2026-11-02",
      start_time: "14:00:00",
      end_time: "16:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    });

    const { findByTestId } = render(<AvailabilityScreen />);
    await findByTestId("override-date-input");

    fireEvent.changeText(await findByTestId("override-date-input"), "2026-11-02");
    fireEvent.changeText(await findByTestId("override-start-input"), "14:00");
    fireEvent.changeText(await findByTestId("override-end-input"), "16:00");
    fireEvent.press(await findByTestId("override-save-permanent"));

    await waitFor(() =>
      expect(createOverride).toHaveBeenCalledWith(
        expect.objectContaining({ apply_to_weekly_template: true }),
      ),
    );
    // Kaydettikten sonra liste (getAvailabilityOverrides) tekrar cekiliyor.
    await waitFor(() => expect(mockedApi.getAvailabilityOverrides).toHaveBeenCalledTimes(2));
  });

  test("mevcut istisna Kaldır ile silinebilir", async () => {
    const override: AvailabilityOverride = {
      id: 302,
      tenant_id: 10,
      staff_id: 1,
      date: "2026-11-03",
      start_time: "10:00:00",
      end_time: "12:00:00",
      mode: "flexible",
      slot_duration_minutes: null,
      gap_minutes: 0,
    };
    mockedApi.getAvailabilityOverrides.mockResolvedValue([override]);
    const removeOverride = mockedApi.removeAvailabilityOverride.mockResolvedValue(undefined);

    const { findByTestId, findByText } = render(<AvailabilityScreen />);
    await findByText(/2026-11-03/);

    fireEvent.press(await findByTestId("override-remove-302"));

    await waitFor(() => expect(removeOverride).toHaveBeenCalledWith(302));
  });

  test("randevu açık kalma süresi kaydedilebilir", async () => {
    const updateSettings = mockedApi.updateBookingSettings.mockResolvedValue({
      ...ownerTenant,
      max_advance_booking_days: 7,
    });

    const { findByTestId } = render(<AvailabilityScreen />);
    await findByTestId("horizon-unlimited-toggle");

    fireEvent(await findByTestId("horizon-unlimited-toggle"), "valueChange", false);
    fireEvent.changeText(await findByTestId("horizon-days-input"), "7");
    fireEvent.press(await findByTestId("horizon-save"));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledWith(7));
  });

  test("staff rolündeki kullanıcı randevu açık kalma süresi bölümünü görmez ve kendi planına kilitlenir", async () => {
    mockedApi.getMyTenant.mockResolvedValue({
      ...ownerTenant,
      my_role: "staff",
      my_staff_member_id: 2,
      my_permissions: ["can_manage_availability"],
    });

    const { findByText, queryByText, queryByTestId } = render(<AvailabilityScreen />);

    await findByText("Kendi çalışma planınız");
    // staff_id=2'ye (Zeynep Usta) kilitlenmis olmali - Cumartesi degil,
    // Zeynep Usta'nin kurali (Carsamba) gorunmeli.
    expect(await findByText(/Çarşamba 10:00–16:00/)).toBeTruthy();
    expect(queryByText("Randevu Açık Kalma Süresi")).toBeNull();
    expect(queryByTestId("staff-filter-1")).toBeNull();
  });
});

import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { api } from "@/lib/api";
import type { AvailabilityRule, StaffMember } from "@/lib/types";
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

const staffMembers: StaffMember[] = [
  { id: 1, tenant_id: 10, name: "Elif Usta", is_active: true },
  { id: 2, tenant_id: 10, name: "Zeynep Usta", is_active: true },
];
const rules: AvailabilityRule[] = [
  { id: 100, tenant_id: 10, staff_id: 1, weekday: 0, start_time: "09:00:00", end_time: "18:00:00" },
  { id: 101, tenant_id: 10, staff_id: 2, weekday: 2, start_time: "10:00:00", end_time: "16:00:00" },
];

function setupDefaultMocks() {
  mockedApi.getStaffMembers.mockResolvedValue(staffMembers);
  mockedApi.getAvailabilityRules.mockResolvedValue(rules);
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

  test("gün ve saat girilip Ekle'ye basınca doğru API çağrısı yapılır", async () => {
    mockedApi.createAvailabilityRule.mockResolvedValue({
      id: 200,
      tenant_id: 10,
      staff_id: 1,
      weekday: 1,
      start_time: "11:00:00",
      end_time: "15:00:00",
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
});

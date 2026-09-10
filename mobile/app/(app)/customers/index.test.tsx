import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";
import CustomersScreen from "./index";

jest.mock("@/lib/api");
// Diger ekran testlerindeki (appointments/new.test.tsx, availability/
// index.test.tsx) ayni sebep: router'i disaridan bir degiskenle factory'ye
// tasimiyoruz - jest.mock hoisting'i yuzunden bu ekranin importu, o degisken
// henuz atanmadan tetiklenebilir ve router "undefined" kalir.
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

const customers: Customer[] = [
  {
    id: 1,
    tenant_id: 10,
    whatsapp_number: "905551112233",
    display_name: "Elif Demir",
    first_seen_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    tenant_id: 10,
    whatsapp_number: "905552223344",
    display_name: "Ahmet Kaya",
    first_seen_at: "2026-01-02T00:00:00Z",
  },
];

describe("CustomersScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getCustomers.mockResolvedValue(customers);
  });

  test("müşteri listesi ad ve telefon ile gösterilir", async () => {
    const { findByText, getByText } = render(<CustomersScreen />);

    expect(await findByText("Elif Demir")).toBeTruthy();
    expect(getByText("905551112233")).toBeTruthy();
    expect(getByText("Ahmet Kaya")).toBeTruthy();
    expect(getByText("905552223344")).toBeTruthy();
  });

  test("arama ile liste ada veya telefona göre filtrelenir", async () => {
    const { findByTestId, findByText, queryByText } = render(<CustomersScreen />);
    await findByText("Elif Demir");

    fireEvent.changeText(await findByTestId("customer-search"), "Ahmet");

    expect(await findByText("Ahmet Kaya")).toBeTruthy();
    expect(queryByText("Elif Demir")).toBeNull();
  });

  test("boş listede uygun mesaj gösterilir", async () => {
    mockedApi.getCustomers.mockResolvedValue([]);
    const { findByText } = render(<CustomersScreen />);
    expect(await findByText("Henüz müşteri yok.")).toBeTruthy();
  });

  test("yeni müşteri ekle ile doğru API çağrısı yapılır ve listede görünür", async () => {
    mockedApi.createCustomer.mockResolvedValue({
      id: 3,
      tenant_id: 10,
      whatsapp_number: "905559998877",
      display_name: "Yeni Müşteri",
      first_seen_at: "2026-09-10T00:00:00Z",
    });

    const { findByTestId, findByText } = render(<CustomersScreen />);
    await findByText("Elif Demir");

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
    expect(await findByText("Yeni Müşteri")).toBeTruthy();
  });
});

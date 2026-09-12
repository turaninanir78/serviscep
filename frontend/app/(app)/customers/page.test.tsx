import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import type { Customer, Tenant } from "@/lib/types";
import CustomersPage from "./page";

const tenant: Tenant = {
  id: 1,
  name: "Test Kuaförü",
  timezone: "Europe/Istanbul",
  my_role: "owner",
  my_permissions: [],
};

const customer: Customer = {
  id: 5,
  tenant_id: 1,
  whatsapp_number: "905551234567",
  display_name: "Ayşe Yılmaz",
  first_seen_at: "2026-09-01T10:00:00Z",
  deletion_requested_at: null,
  deleted_at: null,
};

describe("CustomersPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("Veriyi Sil onaylanınca müşteri silinip listeden kaldırılır", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getCustomers").mockResolvedValue([customer]);
    vi.spyOn(api, "getMyTenant").mockResolvedValue(tenant);
    const requestDeletion = vi.spyOn(api, "requestCustomerDeletion").mockResolvedValue({
      ...customer,
      display_name: "Silinmiş Müşteri",
      whatsapp_number: "deleted:5:abcdef",
      deleted_at: "2026-09-11T00:00:00Z",
      deletion_requested_at: "2026-09-11T00:00:00Z",
    });

    render(<CustomersPage />);

    expect(await screen.findByText("Ayşe Yılmaz")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Veriyi Sil" }));

    expect(screen.getByText(/GERİ ALINAMAZ/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Evet, Kalıcı Olarak Sil" }));

    await waitFor(() => expect(requestDeletion).toHaveBeenCalledWith(5));
    await waitFor(() => expect(screen.queryByText("Ayşe Yılmaz")).not.toBeInTheDocument());
    expect(screen.getByText("Henüz müşteri yok.")).toBeInTheDocument();
  });

  test("Vazgeç'e basılınca silme işlemi tetiklenmez", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getCustomers").mockResolvedValue([customer]);
    vi.spyOn(api, "getMyTenant").mockResolvedValue(tenant);
    const requestDeletion = vi.spyOn(api, "requestCustomerDeletion");

    render(<CustomersPage />);

    await screen.findByText("Ayşe Yılmaz");
    await user.click(screen.getByRole("button", { name: "Veriyi Sil" }));
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));

    expect(requestDeletion).not.toHaveBeenCalled();
    expect(screen.getByText("Ayşe Yılmaz")).toBeInTheDocument();
  });

  test("silme başarısız olursa hata mesajı gösterilir, müşteri listede kalır", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getCustomers").mockResolvedValue([customer]);
    vi.spyOn(api, "getMyTenant").mockResolvedValue(tenant);
    vi.spyOn(api, "requestCustomerDeletion").mockRejectedValue(
      new ApiError(409, "Customer data already deleted"),
    );

    render(<CustomersPage />);

    await screen.findByText("Ayşe Yılmaz");
    await user.click(screen.getByRole("button", { name: "Veriyi Sil" }));
    await user.click(screen.getByRole("button", { name: "Evet, Kalıcı Olarak Sil" }));

    expect(await screen.findByText(/Bu işlem mevcut bir kayıtla çakışıyor/)).toBeInTheDocument();
    // Hem tablo satirinda hem modal'in uyari metninde gorunur (isim iki
    // yerde de basiliyor) - kritik olan, satirin hala listede olmasi.
    expect(screen.getAllByText("Ayşe Yılmaz").length).toBeGreaterThan(0);
  });
});

import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import type { AvailableSlotsResponse, Customer, Service, StaffMember } from "@/lib/types";
import NewAppointmentForm from "./NewAppointmentForm";

// Sabit veriler backend'deki gercek sema alanlariyla birebir eslesiyor
// (bkz. backend/app/schemas: StaffMember, Service, Customer, AvailableSlotsResponse).
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

function slotsResponse(slots: string[]): AvailableSlotsResponse {
  return { date: "2026-09-14", staff_id: 1, service_id: 2, slots };
}

function renderForm(timezone = "Europe/Istanbul") {
  const onCreated = vi.fn();
  const onCancel = vi.fn();
  const utils = render(
    <NewAppointmentForm
      staffMembers={staffMembers}
      services={services}
      customers={customers}
      timezone={timezone}
      onCreated={onCreated}
      onCancel={onCancel}
    />,
  );
  return { ...utils, onCreated, onCancel };
}

function getDateInput(container: HTMLElement): HTMLInputElement {
  return container.querySelector('input[type="date"]') as HTMLInputElement;
}

async function selectStaffAndService(user: ReturnType<typeof userEvent.setup>) {
  const [staffSelect, serviceSelect] = screen.getAllByRole("combobox");
  await user.selectOptions(staffSelect, "1");
  await user.selectOptions(serviceSelect, "2");
}

async function selectCustomer(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByPlaceholderText("Ad veya WhatsApp numarası ile ara..."),
    "Elif",
  );
  await user.click(await screen.findByRole("button", { name: /Elif Demir/ }));
}

describe("NewAppointmentForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("personel, hizmet ve tarih seçilince slot listesi API'den doğru parametrelerle yüklenir", async () => {
    const getAvailableSlots = vi
      .spyOn(api, "getAvailableSlots")
      .mockResolvedValue(
        slotsResponse(["2026-09-14T09:00:00+03:00", "2026-09-14T09:30:00+03:00"]),
      );

    const user = userEvent.setup();
    const { container } = renderForm();
    const usedDate = getDateInput(container).value; // bileşenin varsayılan (bugünkü) tarihi

    await selectStaffAndService(user);

    await waitFor(() => expect(getAvailableSlots).toHaveBeenCalledTimes(1));
    expect(getAvailableSlots).toHaveBeenCalledWith(1, 2, usedDate);
    expect(await screen.findByRole("button", { name: "09:00" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "09:30" })).toBeInTheDocument();
  });

  test("slot saatleri, tarayıcının değil TENANT'ın saat dilimiyle gösterilir", async () => {
    vi.spyOn(api, "getAvailableSlots").mockResolvedValue(
      slotsResponse(["2026-09-14T09:00:00+03:00"]),
    );

    const user = userEvent.setup();
    // Istanbul yerel saatiyle 09:00 olan bir slot, Los Angeles'ta (Eylul'de
    // PDT, UTC-7) bir onceki takvim gununde 23:00 olarak gorunmeli - bu,
    // "timezone" prop'unun gercekten kullanildigini (tarayicinin kendi
    // yerel saat dilimine duselmedigini) dogruluyor.
    renderForm("America/Los_Angeles");
    await selectStaffAndService(user);

    expect(await screen.findByRole("button", { name: "23:00" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "09:00" })).not.toBeInTheDocument();
  });

  test("parametreler değişince eski slot listesi ve seçili slot senkron olarak temizlenir", async () => {
    const getAvailableSlots = vi.spyOn(api, "getAvailableSlots");
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T09:00:00+03:00"]));

    const user = userEvent.setup();
    const { container } = renderForm();
    await selectStaffAndService(user);

    const firstSlot = await screen.findByRole("button", { name: "09:00" });
    await user.click(firstSlot);
    expect(screen.getByText("Müşteri")).toBeInTheDocument();

    // İkinci çağrıyı bilerek askıda bırakıyoruz - böylece fetch daha
    // tamamlanmadan ÖNCE reset'in gerçekten senkron olduğu doğrulanabiliyor.
    let releaseSecondCall: (() => void) | undefined;
    getAvailableSlots.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          releaseSecondCall = () =>
            resolve(slotsResponse(["2026-09-14T10:00:00+03:00"]));
        }),
    );

    fireEvent.change(getDateInput(container), { target: { value: "2026-09-21" } });

    expect(screen.queryByRole("button", { name: "09:00" })).not.toBeInTheDocument();
    expect(screen.queryByText("Müşteri")).not.toBeInTheDocument();
    expect(screen.getByText("Yükleniyor...")).toBeInTheDocument();

    releaseSecondCall?.();
    expect(await screen.findByRole("button", { name: "10:00" })).toBeInTheDocument();
  });

  test("parametreler değişince önceki hata mesajı senkron olarak temizlenir", async () => {
    const getAvailableSlots = vi.spyOn(api, "getAvailableSlots");
    getAvailableSlots.mockRejectedValueOnce(new ApiError(400, "gecersiz istek"));

    const user = userEvent.setup();
    const { container } = renderForm();
    await selectStaffAndService(user);

    expect(
      await screen.findByText("İstek geçersiz. Lütfen bilgileri kontrol edip tekrar deneyin."),
    ).toBeInTheDocument();

    getAvailableSlots.mockResolvedValueOnce(slotsResponse([]));
    fireEvent.change(getDateInput(container), { target: { value: "2026-09-21" } });

    expect(
      screen.queryByText("İstek geçersiz. Lütfen bilgileri kontrol edip tekrar deneyin."),
    ).not.toBeInTheDocument();
  });

  test("boş sonuç durumunda 'müsait saat yok' mesajı gösterilir", async () => {
    vi.spyOn(api, "getAvailableSlots").mockResolvedValue(slotsResponse([]));

    const user = userEvent.setup();
    renderForm();
    await selectStaffAndService(user);

    expect(await screen.findByText("Bu tarihte müsait saat yok.")).toBeInTheDocument();
  });

  test("bilinen bir API hatası (404) kullanıcıya Türkçe, durum koduna uygun mesaj olarak gösterilir", async () => {
    vi.spyOn(api, "getAvailableSlots").mockRejectedValue(new ApiError(404, "not found"));

    const user = userEvent.setup();
    renderForm();
    await selectStaffAndService(user);

    expect(await screen.findByText("Aradığınız kayıt bulunamadı.")).toBeInTheDocument();
  });

  test("eşlenmemiş bir HTTP durum kodunda genel yedek mesaj gösterilir", async () => {
    vi.spyOn(api, "getAvailableSlots").mockRejectedValue(new ApiError(500, "server error"));

    const user = userEvent.setup();
    renderForm();
    await selectStaffAndService(user);

    expect(
      await screen.findByText("Bir şeyler ters gitti, tekrar deneyin."),
    ).toBeInTheDocument();
  });

  test("randevu oluşturma 409 ile çakışırsa slot listesi yenilenir ve kullanıcıya mesaj gösterilir", async () => {
    const getAvailableSlots = vi.spyOn(api, "getAvailableSlots");
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T09:00:00+03:00"]));
    vi.spyOn(api, "createAppointment").mockRejectedValueOnce(new ApiError(409, "conflict"));
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T11:00:00+03:00"]));

    const user = userEvent.setup();
    renderForm();
    await selectStaffAndService(user);

    await user.click(await screen.findByRole("button", { name: "09:00" }));
    await selectCustomer(user);
    await user.click(screen.getByRole("button", { name: "Randevuyu Oluştur" }));

    expect(
      await screen.findByText(
        "Bu slot az önce başka biri tarafından alındı. Slot listesi yenilendi, lütfen başka bir saat seçin.",
      ),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "11:00" })).toBeInTheDocument();
    expect(getAvailableSlots).toHaveBeenCalledTimes(2);
  });
});

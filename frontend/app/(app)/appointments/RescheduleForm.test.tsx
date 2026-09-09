import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import type {
  Appointment,
  AvailableSlotsResponse,
  Customer,
  Service,
  StaffMember,
} from "@/lib/types";
import RescheduleForm from "./RescheduleForm";

// Sabit veriler backend'deki gercek sema alanlariyla birebir eslesiyor
// (bkz. backend/app/schemas: StaffMember, Service, Customer, AppointmentOut,
// AvailableSlotsResponse).
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
const appointment: Appointment = {
  id: 42,
  tenant_id: 10,
  customer_id: 3,
  service_id: 2,
  staff_id: 1,
  start_at: "2026-09-14T09:00:00+03:00",
  end_at: "2026-09-14T09:30:00+03:00",
  status: "pending",
  created_via: "dashboard",
  buffer_minutes: 0,
};

function slotsResponse(slots: string[]): AvailableSlotsResponse {
  return { date: "2026-09-14", staff_id: 1, service_id: 2, slots };
}

function renderForm() {
  const onRescheduled = vi.fn();
  const onCancel = vi.fn();
  const utils = render(
    <RescheduleForm
      appointment={appointment}
      staffMembers={staffMembers}
      services={services}
      customers={customers}
      onRescheduled={onRescheduled}
      onCancel={onCancel}
    />,
  );
  return { ...utils, onRescheduled, onCancel };
}

function getDateInput(container: HTMLElement): HTMLInputElement {
  return container.querySelector('input[type="date"]') as HTMLInputElement;
}

describe("RescheduleForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("mount olduğunda, kullanıcı hiçbir şey yapmadan mevcut tarih için otomatik slot yüklemesi yapılır", async () => {
    const getAvailableSlots = vi
      .spyOn(api, "getAvailableSlots")
      .mockResolvedValue(slotsResponse(["2026-09-14T10:00:00+03:00"]));

    renderForm();

    // slotsLoading baslangic degeri true - mount'ta, fetch daha
    // cozulmeden ONCE spinner senkron olarak gorunur (set-state-in-effect
    // duzeltmesinin dogru calistiginin kaniti).
    expect(screen.getByText("Yükleniyor...")).toBeInTheDocument();

    await waitFor(() => expect(getAvailableSlots).toHaveBeenCalledTimes(1));
    expect(getAvailableSlots).toHaveBeenCalledWith(1, 2, "2026-09-14");
    expect(await screen.findByRole("button", { name: "10:00" })).toBeInTheDocument();
  });

  test("tarih değişince slot listesi yeniden yüklenir ve eski seçim temizlenir", async () => {
    const getAvailableSlots = vi.spyOn(api, "getAvailableSlots");
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T10:00:00+03:00"]));

    const { container } = renderForm();
    const firstSlot = await screen.findByRole("button", { name: "10:00" });
    await userEvent.setup().click(firstSlot);

    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-21T11:00:00+03:00"]));
    fireEvent.change(getDateInput(container), { target: { value: "2026-09-21" } });

    // Eski slot listesi ve secim hemen (senkron) temizleniyor.
    expect(screen.queryByRole("button", { name: "10:00" })).not.toBeInTheDocument();
    expect(screen.getByText("Yükleniyor...")).toBeInTheDocument();

    expect(await screen.findByRole("button", { name: "11:00" })).toBeInTheDocument();
    expect(getAvailableSlots).toHaveBeenLastCalledWith(1, 2, "2026-09-21");
    expect(getAvailableSlots).toHaveBeenCalledTimes(2);
  });

  test("kaydetme başarılı olduğunda doğru API çağrısı yapılır ve onRescheduled tetiklenir", async () => {
    vi.spyOn(api, "getAvailableSlots").mockResolvedValue(
      slotsResponse(["2026-09-14T10:00:00+03:00"]),
    );
    const rescheduleAppointment = vi.spyOn(api, "rescheduleAppointment").mockResolvedValue({
      ...appointment,
      start_at: "2026-09-14T10:00:00+03:00",
    });

    const user = userEvent.setup();
    const { onRescheduled } = renderForm();

    await user.click(await screen.findByRole("button", { name: "10:00" }));
    await user.click(screen.getByRole("button", { name: "Yeni Saati Kaydet" }));

    await waitFor(() =>
      expect(rescheduleAppointment).toHaveBeenCalledWith(42, {
        start_at: "2026-09-14T10:00:00+03:00",
      }),
    );
    expect(onRescheduled).toHaveBeenCalledTimes(1);
  });

  test("kaydetme 409 ile çakışırsa slot listesi yenilenir ve kullanıcıya mesaj gösterilir", async () => {
    const getAvailableSlots = vi.spyOn(api, "getAvailableSlots");
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T10:00:00+03:00"]));
    vi.spyOn(api, "rescheduleAppointment").mockRejectedValueOnce(new ApiError(409, "conflict"));
    getAvailableSlots.mockResolvedValueOnce(slotsResponse(["2026-09-14T11:00:00+03:00"]));

    const user = userEvent.setup();
    renderForm();

    await user.click(await screen.findByRole("button", { name: "10:00" }));
    await user.click(screen.getByRole("button", { name: "Yeni Saati Kaydet" }));

    expect(
      await screen.findByText("Bu slot dolu. Slot listesi yenilendi, lütfen başka bir saat seçin."),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "11:00" })).toBeInTheDocument();
    expect(getAvailableSlots).toHaveBeenCalledTimes(2);
  });
});

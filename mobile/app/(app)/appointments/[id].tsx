import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { StatusBadge, ACTIVE_STATUSES } from "@/components/StatusBadge";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { confirmThen } from "@/lib/confirm";
import { formatDateTime, formatSlotTime, nextNDates, formatDateChip } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";

export default function AppointmentDetailScreen() {
  const { tenantTimezone } = useAuth();
  // Cihazin yerel "bugun"u degil, TENANT'in yerel "bugun"u - bkz.
  // lib/dates.ts basindaki aciklama.
  const rescheduleDateOptions = useMemo(
    () => nextNDates(14, tenantTimezone),
    [tenantTimezone],
  );

  const { id } = useLocalSearchParams<{ id: string }>();
  const appointmentId = Number(id);

  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [service, setService] = useState<Service | null>(null);
  const [staff, setStaff] = useState<StaffMember | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actingOn, setActingOn] = useState<string | null>(null);

  const [rescheduling, setRescheduling] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([
      api.getAppointment(appointmentId),
      api.getCustomers(),
      api.getServices(),
      api.getStaffMembers(),
    ])
      .then(([appointmentData, customers, services, staffMembers]) => {
        setAppointment(appointmentData);
        setCustomer(customers.find((c) => c.id === appointmentData.customer_id) ?? null);
        setService(services.find((s) => s.id === appointmentData.service_id) ?? null);
        setStaff(staffMembers.find((s) => s.id === appointmentData.staff_id) ?? null);
      })
      .catch((err) => setError(describeApiError(err)));
  }, [appointmentId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  function loadSlots(forDate: string) {
    if (!appointment) return;
    setSlotsLoading(true);
    setSlotsError(null);
    setSelectedSlot(null);
    api
      .getAvailableSlots(appointment.staff_id, appointment.service_id, forDate)
      .then((res) => setSlots(res.slots))
      .catch((err) => {
        setSlots(null);
        setSlotsError(describeApiError(err));
      })
      .finally(() => setSlotsLoading(false));
  }

  function openReschedule() {
    setRescheduling(true);
    const firstDate = rescheduleDateOptions[0];
    setSelectedDate(firstDate);
    loadSlots(firstDate);
  }

  function handleSelectDate(date: string) {
    setSelectedDate(date);
    loadSlots(date);
  }

  async function handleConfirmReschedule() {
    if (!selectedSlot) return;
    setActingOn("reschedule");
    try {
      await api.rescheduleAppointment(appointmentId, { start_at: selectedSlot });
      setRescheduling(false);
      load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setSlotsError("Bu slot dolu. Slot listesi yenilendi, lütfen başka bir saat seçin.");
        if (selectedDate) loadSlots(selectedDate);
      } else {
        setSlotsError(describeApiError(err));
      }
    } finally {
      setActingOn(null);
    }
  }

  async function runAction(key: string, action: () => Promise<Appointment>) {
    setActingOn(key);
    setError(null);
    try {
      await action();
      load();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setActingOn(null);
    }
  }

  if (error && !appointment) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!appointment) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  const isActive = ACTIVE_STATUSES.has(appointment.status);
  const busy = actingOn !== null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16, gap: 16 }}>
      <View style={styles.card}>
        <StatusBadge status={appointment.status} />
        <Text style={styles.customerName}>
          {customer?.display_name || customer?.whatsapp_number || `#${appointment.customer_id}`}
        </Text>
        <Text style={styles.detailLine}>{service?.name ?? `#${appointment.service_id}`}</Text>
        <Text style={styles.detailLine}>{staff?.name ?? `#${appointment.staff_id}`}</Text>
        <Text style={styles.detailLine}>{formatDateTime(appointment.start_at, tenantTimezone)}</Text>
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      {isActive && !rescheduling && (
        <View style={styles.actions}>
          {appointment.status === "pending" && (
            <ActionButton
              label="Onayla"
              disabled={busy}
              busy={actingOn === "confirm"}
              onPress={() =>
                confirmThen("Bu randevu onaylandı olarak işaretlensin mi?", () =>
                  runAction("confirm", () => api.confirmAppointment(appointmentId)),
                )
              }
            />
          )}
          <ActionButton
            label="Yeniden Planla"
            disabled={busy}
            onPress={openReschedule}
          />
          <ActionButton
            label="Tamamlandı"
            disabled={busy}
            busy={actingOn === "complete"}
            onPress={() =>
              confirmThen("Bu randevu tamamlandı olarak işaretlensin mi?", () =>
                runAction("complete", () => api.completeAppointment(appointmentId)),
              )
            }
          />
          <ActionButton
            label="Gelmedi"
            disabled={busy}
            busy={actingOn === "no_show"}
            onPress={() =>
              confirmThen("Bu randevu 'gelmedi' olarak işaretlensin mi?", () =>
                runAction("no_show", () => api.markAppointmentNoShow(appointmentId)),
              )
            }
          />
          <ActionButton
            label="İptal Et"
            disabled={busy}
            busy={actingOn === "cancel"}
            destructive
            onPress={() =>
              confirmThen("Bu randevuyu iptal etmek istediğinize emin misiniz?", () =>
                runAction("cancel", () => api.cancelAppointment(appointmentId)),
              )
            }
          />
        </View>
      )}

      {rescheduling && (
        <View style={styles.card}>
          <View style={styles.rescheduleHeader}>
            <Text style={styles.sectionTitle}>Yeniden Planla</Text>
            <Pressable onPress={() => setRescheduling(false)}>
              <Text style={styles.link}>Vazgeç</Text>
            </Pressable>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.dateRow}>
            {rescheduleDateOptions.map((date) => (
              <Pressable
                key={date}
                onPress={() => handleSelectDate(date)}
                style={[styles.dateChip, selectedDate === date && styles.dateChipActive]}
              >
                <Text
                  style={[
                    styles.dateChipText,
                    selectedDate === date && styles.dateChipTextActive,
                  ]}
                >
                  {formatDateChip(date)}
                </Text>
              </Pressable>
            ))}
          </ScrollView>

          {slotsLoading && <ActivityIndicator style={{ marginTop: 12 }} />}
          {slotsError && <Text style={styles.error}>{slotsError}</Text>}
          {!slotsLoading && !slotsError && slots !== null && slots.length === 0 && (
            <Text style={styles.detailLine}>Bu tarihte müsait saat yok.</Text>
          )}
          {!slotsLoading && slots !== null && slots.length > 0 && (
            <View style={styles.slotGrid}>
              {slots.map((slot) => (
                <Pressable
                  key={slot}
                  onPress={() => setSelectedSlot(slot)}
                  style={[styles.slotChip, selectedSlot === slot && styles.slotChipActive]}
                >
                  <Text
                    style={[
                      styles.slotChipText,
                      selectedSlot === slot && styles.slotChipTextActive,
                    ]}
                  >
                    {formatSlotTime(slot, tenantTimezone)}
                  </Text>
                </Pressable>
              ))}
            </View>
          )}

          <Pressable
            style={[styles.saveButton, (!selectedSlot || busy) && styles.buttonDisabled]}
            disabled={!selectedSlot || busy}
            onPress={handleConfirmReschedule}
            testID="reschedule-save"
          >
            {actingOn === "reschedule" ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Yeni Saati Kaydet</Text>
            )}
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function ActionButton({
  label,
  onPress,
  disabled,
  busy,
  destructive,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  destructive?: boolean;
}) {
  return (
    <Pressable
      style={[styles.actionButton, destructive && styles.actionButtonDestructive]}
      onPress={onPress}
      disabled={disabled}
      testID={`action-${label}`}
    >
      {busy ? (
        <ActivityIndicator size="small" color={destructive ? "#991b1b" : "#000"} />
      ) : (
        <Text style={[styles.actionButtonText, destructive && styles.actionButtonTextDestructive]}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafafa" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    gap: 6,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  customerName: { fontSize: 18, fontWeight: "700", marginTop: 4 },
  detailLine: { fontSize: 14, color: "#3f3f46" },
  error: { color: "#dc2626" },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  actionButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minWidth: 96,
    alignItems: "center",
  },
  actionButtonDestructive: { borderColor: "#fecaca" },
  actionButtonText: { fontSize: 13, fontWeight: "600", color: "#000" },
  actionButtonTextDestructive: { color: "#991b1b" },
  rescheduleHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  sectionTitle: { fontSize: 16, fontWeight: "700" },
  link: { color: "#71717a", textDecorationLine: "underline" },
  dateRow: { flexGrow: 0, marginTop: 12 },
  dateChip: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
  },
  dateChipActive: { backgroundColor: "#000", borderColor: "#000" },
  dateChipText: { fontSize: 13, color: "#000" },
  dateChipTextActive: { color: "#fff" },
  slotGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  slotChip: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  slotChipActive: { backgroundColor: "#000", borderColor: "#000" },
  slotChipText: { fontSize: 13, color: "#000" },
  slotChipTextActive: { color: "#fff" },
  saveButton: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 16,
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontWeight: "600" },
});

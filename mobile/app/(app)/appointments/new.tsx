import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { QuickCustomerForm } from "@/components/QuickCustomerForm";
import { api, ApiError } from "@/lib/api";
import { formatDateChip, formatSlotTime, nextNDates } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Customer, Service, StaffMember } from "@/lib/types";

const DATE_OPTIONS = nextNDates(14);

export default function NewAppointmentScreen() {
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [staffId, setStaffId] = useState<number | null>(null);
  const [serviceId, setServiceId] = useState<number | null>(null);
  const [date, setDate] = useState(DATE_OPTIONS[0]);

  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  // Personel/hizmet/tarih hizlica art arda degistirilirse birden fazla slot
  // istegi ayni anda ucabilir - erken baslayan bir istek GEC donerse, guncel
  // secimin sonucunu eski veriyle ezmemesi icin her istege bir siralama
  // numarasi veriyoruz ve sadece "hala en guncel istek" ise state'i yaziyoruz.
  const slotsRequestRef = useRef(0);

  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [showNewCustomer, setShowNewCustomer] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoadError(null);
    Promise.all([api.getStaffMembers(), api.getServices(), api.getCustomers()])
      .then(([staffData, servicesData, customersData]) => {
        setStaffMembers(staffData);
        setServices(servicesData);
        setCustomers(customersData);
      })
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  function loadSlots(nextStaffId: number, nextServiceId: number, nextDate: string) {
    const requestId = ++slotsRequestRef.current;
    api
      .getAvailableSlots(nextStaffId, nextServiceId, nextDate)
      .then((res) => {
        if (requestId !== slotsRequestRef.current) return;
        setSlots(res.slots);
      })
      .catch((err) => {
        if (requestId !== slotsRequestRef.current) return;
        setSlots(null);
        setSlotsError(describeApiError(err));
      })
      .finally(() => {
        if (requestId !== slotsRequestRef.current) return;
        setSlotsLoading(false);
      });
  }

  function refreshSlots(nextStaffId: number | null, nextServiceId: number | null, nextDate: string) {
    if (!nextStaffId || !nextServiceId) {
      slotsRequestRef.current += 1; // olasi bir eski istegi de gecersiz kil
      setSlots(null);
      setSlotsLoading(false);
      setSlotsError(null);
      setSelectedSlot(null);
      return;
    }
    setSlotsLoading(true);
    setSlotsError(null);
    setSelectedSlot(null);
    loadSlots(nextStaffId, nextServiceId, nextDate);
  }

  function handleSelectStaff(id: number) {
    setStaffId(id);
    refreshSlots(id, serviceId, date);
  }

  function handleSelectService(id: number) {
    setServiceId(id);
    refreshSlots(staffId, id, date);
  }

  function handleSelectDate(value: string) {
    setDate(value);
    refreshSlots(staffId, serviceId, value);
  }

  const activeStaff = staffMembers.filter((s) => s.is_active);
  const activeServices = services.filter((s) => s.is_active);

  const filteredCustomers =
    customerSearch.trim() === ""
      ? []
      : customers
          .filter((c) => {
            const term = customerSearch.trim().toLowerCase();
            return (
              (c.display_name ?? "").toLowerCase().includes(term) ||
              c.whatsapp_number.includes(term)
            );
          })
          .slice(0, 20);

  function handleCustomerCreated(customer: Customer) {
    setCustomers((prev) => [...prev, customer]);
    setSelectedCustomer(customer);
    setShowNewCustomer(false);
    setCustomerSearch("");
  }

  async function handleSubmit() {
    if (!staffId || !serviceId || !selectedSlot || !selectedCustomer) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await api.createAppointment({
        staff_id: staffId,
        service_id: serviceId,
        customer_id: selectedCustomer.id,
        start_at: selectedSlot,
      });
      router.back();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFormError(
          "Bu slot az önce başka biri tarafından alındı. Slot listesi yenilendi, lütfen başka bir saat seçin.",
        );
        refreshSlots(staffId, serviceId, date);
      } else {
        setFormError(describeApiError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{loadError}</Text>
      </View>
    );
  }

  const busy = submitting;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16, gap: 16 }}>
      {(activeStaff.length === 0 || activeServices.length === 0) ? (
        <Text style={styles.detailLine}>
          Randevu oluşturmak için en az bir aktif personel ve bir aktif hizmet gerekiyor.
        </Text>
      ) : (
        <>
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Personel</Text>
            <View style={styles.chipRow}>
              {activeStaff.map((staff) => (
                <Pressable
                  key={staff.id}
                  testID={`staff-option-${staff.id}`}
                  onPress={() => handleSelectStaff(staff.id)}
                  style={[styles.chip, staffId === staff.id && styles.chipActive]}
                >
                  <Text style={[styles.chipText, staffId === staff.id && styles.chipTextActive]}>
                    {staff.name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Hizmet</Text>
            <View style={styles.chipRow}>
              {activeServices.map((service) => (
                <Pressable
                  key={service.id}
                  testID={`service-option-${service.id}`}
                  onPress={() => handleSelectService(service.id)}
                  style={[styles.chip, serviceId === service.id && styles.chipActive]}
                >
                  <Text
                    style={[styles.chipText, serviceId === service.id && styles.chipTextActive]}
                  >
                    {service.name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Tarih</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {DATE_OPTIONS.map((d) => (
                <Pressable
                  key={d}
                  testID={`date-chip-${d}`}
                  onPress={() => handleSelectDate(d)}
                  style={[styles.dateChip, date === d && styles.chipActive]}
                >
                  <Text style={[styles.chipText, date === d && styles.chipTextActive]}>
                    {formatDateChip(d)}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          {staffId && serviceId && (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Müsait Saatler</Text>
              {slotsLoading && <ActivityIndicator style={{ marginTop: 8 }} />}
              {slotsError && <Text style={styles.error}>{slotsError}</Text>}
              {!slotsLoading && !slotsError && slots !== null && slots.length === 0 && (
                <Text style={styles.detailLine}>Bu tarihte müsait saat yok.</Text>
              )}
              {!slotsLoading && slots !== null && slots.length > 0 && (
                <View style={styles.chipRow}>
                  {slots.map((slot) => (
                    <Pressable
                      key={slot}
                      testID={`slot-chip-${slot}`}
                      onPress={() => setSelectedSlot(slot)}
                      style={[styles.chip, selectedSlot === slot && styles.chipActive]}
                    >
                      <Text
                        style={[styles.chipText, selectedSlot === slot && styles.chipTextActive]}
                      >
                        {formatSlotTime(slot)}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              )}
            </View>
          )}

          {selectedSlot && (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Müşteri</Text>
              {selectedCustomer ? (
                <View style={styles.customerRow}>
                  <Text style={styles.detailLine}>
                    {selectedCustomer.display_name || selectedCustomer.whatsapp_number}
                  </Text>
                  <Pressable
                    onPress={() => {
                      setSelectedCustomer(null);
                      setCustomerSearch("");
                    }}
                  >
                    <Text style={styles.link}>Değiştir</Text>
                  </Pressable>
                </View>
              ) : (
                <>
                  <TextInput
                    testID="customer-search-input"
                    placeholder="Ad veya WhatsApp numarası ile ara..."
                    value={customerSearch}
                    onChangeText={setCustomerSearch}
                    style={styles.input}
                  />
                  {filteredCustomers.map((customer) => (
                    <Pressable
                      key={customer.id}
                      testID={`customer-option-${customer.id}`}
                      onPress={() => {
                        setSelectedCustomer(customer);
                        setCustomerSearch("");
                      }}
                      style={styles.customerOption}
                    >
                      <Text style={styles.detailLine}>
                        {customer.display_name || "-"} ({customer.whatsapp_number})
                      </Text>
                    </Pressable>
                  ))}
                  {customerSearch.trim() !== "" && filteredCustomers.length === 0 && (
                    <Text style={styles.detailLine}>Sonuç yok.</Text>
                  )}

                  {!showNewCustomer ? (
                    <Pressable
                      testID="new-customer-toggle"
                      onPress={() => setShowNewCustomer(true)}
                    >
                      <Text style={styles.link}>+ Yeni müşteri ekle</Text>
                    </Pressable>
                  ) : (
                    <View style={styles.newCustomerForm}>
                      <QuickCustomerForm onCreated={handleCustomerCreated} />
                    </View>
                  )}
                </>
              )}
            </View>
          )}

          {formError && <Text style={styles.error}>{formError}</Text>}

          <Pressable
            testID="new-appointment-submit"
            style={[
              styles.saveButton,
              (!selectedSlot || !selectedCustomer || busy) && styles.buttonDisabled,
            ]}
            disabled={!selectedSlot || !selectedCustomer || busy}
            onPress={handleSubmit}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Randevuyu Oluştur</Text>
            )}
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafafa" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    gap: 10,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  sectionTitle: { fontSize: 14, fontWeight: "700" },
  detailLine: { fontSize: 14, color: "#3f3f46" },
  error: { color: "#dc2626" },
  link: { color: "#71717a", textDecorationLine: "underline" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  dateChip: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
  },
  chipActive: { backgroundColor: "#000", borderColor: "#000" },
  chipText: { fontSize: 13, color: "#000" },
  chipTextActive: { color: "#fff" },
  customerRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  customerOption: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#f4f4f5",
  },
  input: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  newCustomerForm: { gap: 8, marginTop: 4 },
  saveButton: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontWeight: "600" },
});

import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";

export default function CustomerDetailScreen() {
  const { tenantTimezone } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  const customerId = Number(id);

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    // Backend'in /appointments'i customer_id'ye gore filtrelemesi yok - tum
    // randevulari cekip client-side filtreliyoruz (availability_rules'i
    // personele gore filtrelerken kullanilan ayni yaklasim).
    Promise.all([
      api.getCustomer(customerId),
      api.getAppointments(),
      api.getServices(),
      api.getStaffMembers(),
    ])
      .then(([customerData, appointmentsData, servicesData, staffData]) => {
        setCustomer(customerData);
        setAppointments(appointmentsData.filter((a) => a.customer_id === customerId));
        setServices(servicesData);
        setStaffMembers(staffData);
      })
      .catch((err) => setError(describeApiError(err)));
  }, [customerId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  function serviceLabel(id: number): string {
    return services.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  function staffLabel(id: number): string {
    return staffMembers.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!customer) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.customerName}>
          {customer.display_name || customer.whatsapp_number}
        </Text>
        <Text style={styles.detailLine}>{customer.whatsapp_number}</Text>
        <Text style={styles.detailLine}>
          İlk görülme: {formatDateTime(customer.first_seen_at, tenantTimezone)}
        </Text>
      </View>

      <Text style={styles.sectionTitle}>Randevu Geçmişi</Text>

      {appointments.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyText}>Bu müşterinin randevusu yok.</Text>
        </View>
      ) : (
        <FlatList
          data={appointments}
          keyExtractor={(item) => String(item.id)}
          testID="customer-appointments-list"
          renderItem={({ item }) => (
            <Pressable
              style={styles.row}
              onPress={() => router.push(`/(app)/appointments/${item.id}`)}
              testID={`customer-appointment-row-${item.id}`}
            >
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle}>
                  {serviceLabel(item.service_id)} — {staffLabel(item.staff_id)}
                </Text>
                <Text style={styles.rowSubtitle}>{formatDateTime(item.start_at, tenantTimezone)}</Text>
              </View>
              <StatusBadge status={item.status} />
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafafa" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  card: {
    backgroundColor: "#fff",
    margin: 16,
    marginBottom: 8,
    borderRadius: 12,
    padding: 16,
    gap: 6,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  customerName: { fontSize: 18, fontWeight: "700" },
  detailLine: { fontSize: 14, color: "#3f3f46" },
  sectionTitle: { fontSize: 14, fontWeight: "700", marginHorizontal: 16, marginBottom: 4 },
  emptyText: { color: "#71717a" },
  error: { color: "#dc2626" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fff",
  },
  rowMain: { flex: 1, gap: 2, marginRight: 12 },
  rowTitle: { fontSize: 15, fontWeight: "600", color: "#000" },
  rowSubtitle: { fontSize: 13, color: "#71717a" },
});

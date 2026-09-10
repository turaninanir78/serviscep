import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";

export default function AppointmentsScreen() {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(() => {
    Promise.all([
      api.getAppointments(),
      api.getCustomers(),
      api.getServices(),
      api.getStaffMembers(),
    ])
      .then(([appointmentsData, customersData, servicesData, staffData]) => {
        setAppointments(appointmentsData);
        setCustomers(customersData);
        setServices(servicesData);
        setStaffMembers(staffData);
      })
      .catch((err) => setError(describeApiError(err)));
  }, []);

  // Detay ekranindan (durum degisikligi/yeniden planlama sonrasi) geri
  // donulunce liste otomatik tazelensin diye useEffect degil useFocusEffect -
  // ekran her odaklandiginda (ilk acilis dahil) calisir.
  useFocusEffect(
    useCallback(() => {
      loadAll();
    }, [loadAll]),
  );

  function customerLabel(id: number): string {
    const customer = customers.find((c) => c.id === id);
    return customer?.display_name || customer?.whatsapp_number || `#${id}`;
  }

  function serviceLabel(id: number): string {
    return services.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  function staffLabel(id: number): string {
    return staffMembers.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  return (
    <View style={styles.container}>
      <NavRow active="appointments" />

      {error && (
        <Text style={styles.error} testID="appointments-error">
          {error}
        </Text>
      )}

      {!error && appointments === null && (
        <View style={styles.center}>
          <ActivityIndicator />
        </View>
      )}

      {!error && appointments !== null && appointments.length === 0 && (
        <View style={styles.center}>
          <Text style={styles.emptyText}>Henüz randevu yok.</Text>
        </View>
      )}

      {!error && appointments !== null && appointments.length > 0 && (
        <FlatList
          data={appointments}
          keyExtractor={(item) => String(item.id)}
          testID="appointments-list"
          renderItem={({ item }) => (
            <Pressable
              style={styles.row}
              onPress={() => router.push(`/(app)/appointments/${item.id}`)}
              testID={`appointment-row-${item.id}`}
            >
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle}>{customerLabel(item.customer_id)}</Text>
                <Text style={styles.rowSubtitle}>
                  {serviceLabel(item.service_id)} — {staffLabel(item.staff_id)}
                </Text>
                <Text style={styles.rowSubtitle}>{formatDateTime(item.start_at)}</Text>
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
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  emptyText: { color: "#71717a" },
  error: { color: "#dc2626", padding: 16 },
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

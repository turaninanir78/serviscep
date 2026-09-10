import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { QuickCustomerForm } from "@/components/QuickCustomerForm";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { Customer } from "@/lib/types";

export default function CustomersScreen() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showNewCustomer, setShowNewCustomer] = useState(false);

  const load = useCallback(() => {
    setError(null);
    api
      .getCustomers()
      .then(setCustomers)
      .catch((err) => setError(describeApiError(err)));
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  // Backend'in list endpoint'i arama/query param desteklemiyor (bkz.
  // GET /customers) - client-side filtreleme yeterli, tenant basina
  // musteri sayisi bu olcekte buyuk bir sorun degil.
  const filtered = (customers ?? []).filter((c) => {
    const term = search.trim().toLowerCase();
    if (term === "") return true;
    return (
      (c.display_name ?? "").toLowerCase().includes(term) || c.whatsapp_number.includes(term)
    );
  });

  function handleCreated(customer: Customer) {
    setCustomers((prev) => (prev ? [...prev, customer] : [customer]));
    setShowNewCustomer(false);
  }

  return (
    <View style={styles.container}>
      <NavRow active="customers" />

      <View style={styles.topSection}>
        <TextInput
          testID="customer-search"
          placeholder="Ad veya WhatsApp numarası ile ara..."
          value={search}
          onChangeText={setSearch}
          style={styles.input}
        />

        {!showNewCustomer ? (
          <Pressable
            testID="new-customer-toggle"
            style={styles.addButton}
            onPress={() => setShowNewCustomer(true)}
          >
            <Text style={styles.addButtonText}>+ Yeni Müşteri</Text>
          </Pressable>
        ) : (
          <View style={styles.newCustomerCard}>
            <QuickCustomerForm onCreated={handleCreated} />
            <Pressable onPress={() => setShowNewCustomer(false)}>
              <Text style={styles.link}>Vazgeç</Text>
            </Pressable>
          </View>
        )}
      </View>

      {error && (
        <Text style={styles.error} testID="customers-error">
          {error}
        </Text>
      )}

      {!error && customers === null && (
        <View style={styles.center}>
          <ActivityIndicator />
        </View>
      )}

      {!error && customers !== null && filtered.length === 0 && (
        <View style={styles.center}>
          <Text style={styles.emptyText}>
            {customers.length === 0 ? "Henüz müşteri yok." : "Sonuç yok."}
          </Text>
        </View>
      )}

      {!error && customers !== null && filtered.length > 0 && (
        <FlatList
          data={filtered}
          keyExtractor={(item) => String(item.id)}
          testID="customers-list"
          renderItem={({ item }) => (
            <Pressable
              style={styles.row}
              onPress={() => router.push(`/(app)/customers/${item.id}`)}
              testID={`customer-row-${item.id}`}
            >
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle}>{item.display_name || "-"}</Text>
                <Text style={styles.rowSubtitle}>{item.whatsapp_number}</Text>
              </View>
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
  topSection: {
    padding: 16,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fff",
  },
  input: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  addButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  addButtonText: { fontSize: 14, fontWeight: "600", color: "#000" },
  newCustomerCard: { gap: 8 },
  link: { color: "#71717a", textDecorationLine: "underline", textAlign: "center" },
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
  rowMain: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 15, fontWeight: "600", color: "#000" },
  rowSubtitle: { fontSize: 13, color: "#71717a" },
});

import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";

import { NavRow } from "@/components/NavRow";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { Service } from "@/lib/types";

export default function ServicesScreen() {
  const [services, setServices] = useState<Service[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api
        .getServices()
        .then(setServices)
        .catch((err) => setError(describeApiError(err)));
    }, []),
  );

  return (
    <View style={styles.container}>
      <NavRow active="services" />

      {error && <Text style={styles.error}>{error}</Text>}

      {!error && services === null && (
        <View style={styles.center}>
          <ActivityIndicator />
        </View>
      )}

      {!error && services !== null && services.length === 0 && (
        <View style={styles.center}>
          <Text style={styles.emptyText}>Henüz hizmet yok.</Text>
        </View>
      )}

      {!error && services !== null && services.length > 0 && (
        <FlatList
          data={services}
          keyExtractor={(item) => String(item.id)}
          testID="services-list"
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle}>{item.name}</Text>
                <Text style={styles.rowSubtitle}>
                  {item.duration_minutes} dk
                  {item.default_buffer_minutes > 0 ? ` · +${item.default_buffer_minutes} dk buffer` : ""}
                  {item.price ? ` · ${item.price}` : ""}
                </Text>
              </View>
              <Text style={item.is_active ? styles.badgeActive : styles.badgeInactive}>
                {item.is_active ? "Aktif" : "Pasif"}
              </Text>
            </View>
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
  badgeActive: { color: "#166534", fontSize: 13, fontWeight: "600" },
  badgeInactive: { color: "#71717a", fontSize: 13, fontWeight: "600" },
});

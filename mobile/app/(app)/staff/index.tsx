import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";

import { NavRow } from "@/components/NavRow";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { StaffMember } from "@/lib/types";

export default function StaffScreen() {
  const [staffMembers, setStaffMembers] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api
        .getStaffMembers()
        .then(setStaffMembers)
        .catch((err) => setError(describeApiError(err)));
    }, []),
  );

  return (
    <View style={styles.container}>
      <NavRow active="staff" />

      {error && <Text style={styles.error}>{error}</Text>}

      {!error && staffMembers === null && (
        <View style={styles.center}>
          <ActivityIndicator />
        </View>
      )}

      {!error && staffMembers !== null && staffMembers.length === 0 && (
        <View style={styles.center}>
          <Text style={styles.emptyText}>Henüz personel yok.</Text>
        </View>
      )}

      {!error && staffMembers !== null && staffMembers.length > 0 && (
        <FlatList
          data={staffMembers}
          keyExtractor={(item) => String(item.id)}
          testID="staff-list"
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.rowTitle}>{item.name}</Text>
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
  rowTitle: { fontSize: 15, fontWeight: "600", color: "#000" },
  badgeActive: { color: "#166534", fontSize: 13, fontWeight: "600" },
  badgeInactive: { color: "#71717a", fontSize: 13, fontWeight: "600" },
});

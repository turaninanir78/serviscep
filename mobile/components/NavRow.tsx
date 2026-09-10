import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

const LINKS = [
  { href: "/(app)/appointments" as const, label: "Randevular" },
  { href: "/(app)/staff" as const, label: "Personel" },
  { href: "/(app)/services" as const, label: "Hizmetler" },
  { href: "/(app)/availability" as const, label: "Müsaitlik" },
];

export function NavRow({
  active,
}: {
  active: "appointments" | "staff" | "services" | "availability";
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.row}>
      {LINKS.map((link) => {
        const isActive = link.href.endsWith(active);
        return (
          <Pressable
            key={link.href}
            onPress={() => router.replace(link.href)}
            style={[styles.tab, isActive && styles.tabActive]}
          >
            <Text style={[styles.tabText, isActive && styles.tabTextActive]}>{link.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    flexGrow: 0,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fff",
  },
  tab: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: "#000",
  },
  tabText: {
    color: "#71717a",
    fontSize: 14,
    fontWeight: "500",
  },
  tabTextActive: {
    color: "#000",
  },
});

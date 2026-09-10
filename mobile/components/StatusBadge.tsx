import { StyleSheet, Text, View } from "react-native";

// Web'in frontend/app/(app)/appointments/page.tsx dosyasindaki
// STATUS_LABELS/STATUS_BADGE_STYLES ile ayni sozlesme.
const STATUS_LABELS: Record<string, string> = {
  pending: "Beklemede",
  confirmed: "Onaylandı",
  cancelled: "İptal Edildi",
  completed: "Tamamlandı",
  no_show: "Gelmedi",
};

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  pending: { bg: "#fef9c3", fg: "#854d0e" },
  confirmed: { bg: "#dbeafe", fg: "#1e40af" },
  cancelled: { bg: "#e4e4e7", fg: "#52525b" },
  completed: { bg: "#dcfce7", fg: "#166534" },
  no_show: { bg: "#fee2e2", fg: "#991b1b" },
};

const FALLBACK_COLOR = { bg: "#e4e4e7", fg: "#52525b" };

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? FALLBACK_COLOR;
  return (
    <View style={[styles.badge, { backgroundColor: color.bg }]}>
      <Text style={[styles.text, { color: color.fg }]}>{STATUS_LABELS[status] ?? status}</Text>
    </View>
  );
}

export const ACTIVE_STATUSES = new Set(["pending", "confirmed"]);

const styles = StyleSheet.create({
  badge: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
  },
});

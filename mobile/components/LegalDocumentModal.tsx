import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "@/lib/api";
import type { LegalDocument } from "@/lib/types";

const TYPE_LABELS: Record<string, string> = {
  terms_of_service: "Kullanım Şartları",
  privacy_notice: "Aydınlatma Metni",
};

export function LegalDocumentModal({ type, onClose }: { type: string; onClose: () => void }) {
  const [document, setDocument] = useState<LegalDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getLegalDocument(type)
      .then((doc) => {
        if (!cancelled) setDocument(doc);
      })
      .catch(() => {
        if (!cancelled) setError("Doküman yüklenemedi.");
      });
    return () => {
      cancelled = true;
    };
  }, [type]);

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <View style={styles.header}>
            <Text style={styles.title}>
              {TYPE_LABELS[type] ?? type}
              {document ? ` (${document.version})` : ""}
            </Text>
            <Pressable onPress={onClose} testID="legal-modal-close">
              <Text style={styles.closeText}>Kapat</Text>
            </Pressable>
          </View>

          {error && <Text style={styles.error}>{error}</Text>}
          {!error && !document && <Text style={styles.hint}>Yükleniyor...</Text>}
          {document && (
            <ScrollView>
              <Text style={styles.content}>{document.content}</Text>
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    padding: 20,
  },
  card: {
    maxHeight: "80%",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 20,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  title: { fontSize: 16, fontWeight: "700" },
  closeText: { color: "#71717a", textDecorationLine: "underline" },
  error: { color: "#dc2626" },
  hint: { color: "#71717a" },
  content: { fontSize: 14, color: "#3f3f46", lineHeight: 20 },
});

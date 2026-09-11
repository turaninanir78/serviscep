import { Redirect, router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { LegalDocumentModal } from "@/components/LegalDocumentModal";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { LegalDocument } from "@/lib/types";

export default function AppLayout() {
  const { isLoading, isAuthenticated, tenantName, logout } = useAuth();
  const [pendingDocuments, setPendingDocuments] = useState<LegalDocument[]>([]);
  const [consentChecked, setConsentChecked] = useState(false);
  const [viewingDocumentType, setViewingDocumentType] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    // Bir hukuki dokuman yeni bir versiyona guncellenmisse (bkz.
    // backend/app/legal.py), kullaniciyi panele sokmadan once onaylatmasi
    // gerekiyor - basit bir tetikleme mantigi: durum alinamazsa kullaniciyi
    // KILITLEMIYORUZ, sessizce devam ediyoruz.
    api
      .getConsentStatus()
      .then((status) => {
        if (!cancelled) setPendingDocuments(status.pending_documents);
      })
      .catch(() => {
        // yut - yukarida aciklandigi gibi
      })
      .finally(() => {
        if (!cancelled) setConsentChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  async function handleAcceptPendingDocuments() {
    setAccepting(true);
    try {
      for (const document of pendingDocuments) {
        await api.acceptDocument(document.id);
      }
      setPendingDocuments([]);
    } finally {
      setAccepting(false);
    }
  }

  if (isLoading || (isAuthenticated && !consentChecked)) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href="/login" />;
  }

  if (pendingDocuments.length > 0) {
    return (
      <View style={styles.consentScreen}>
        <View style={styles.consentCard}>
          <Text style={styles.consentTitle}>Güncellenen şartları onaylayın</Text>
          <Text style={styles.consentHint}>
            Devam etmeden önce aşağıdaki güncellenen belgeleri onaylamanız gerekiyor.
          </Text>
          {pendingDocuments.map((document) => (
            <Pressable key={document.id} onPress={() => setViewingDocumentType(document.type)}>
              <Text style={styles.consentDocLink}>
                {document.type} ({document.version})
              </Text>
            </Pressable>
          ))}
          <Pressable
            style={[styles.consentButton, accepting && styles.consentButtonDisabled]}
            onPress={handleAcceptPendingDocuments}
            disabled={accepting}
            testID="accept-pending-consent"
          >
            {accepting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.consentButtonText}>Kabul Ediyorum</Text>
            )}
          </Pressable>
          <Pressable onPress={handleLogout}>
            <Text style={styles.consentLogoutLink}>Çıkış Yap</Text>
          </Pressable>
        </View>

        {viewingDocumentType && (
          <LegalDocumentModal
            type={viewingDocumentType}
            onClose={() => setViewingDocumentType(null)}
          />
        )}
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerTitle: tenantName ?? "ServisCep",
        headerRight: () => (
          <Pressable onPress={handleLogout} testID="logout-button" hitSlop={8}>
            <Text style={{ color: "#000", fontWeight: "600" }}>Çıkış</Text>
          </Pressable>
        ),
      }}
    >
      <Stack.Screen name="appointments/index" options={{ title: "Randevular" }} />
      <Stack.Screen name="appointments/new" options={{ title: "Yeni Randevu" }} />
      <Stack.Screen name="appointments/[id]" options={{ title: "Randevu Detayı" }} />
      <Stack.Screen name="staff/index" options={{ title: "Personel" }} />
      <Stack.Screen name="services/index" options={{ title: "Hizmetler" }} />
      <Stack.Screen name="availability/index" options={{ title: "Müsaitlik" }} />
      <Stack.Screen name="customers/index" options={{ title: "Müşteriler" }} />
      <Stack.Screen name="customers/[id]" options={{ title: "Müşteri Detayı" }} />
      <Stack.Screen name="profile/index" options={{ title: "Hesabım" }} />
    </Stack>
  );
}

const styles = StyleSheet.create({
  consentScreen: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fafafa" },
  consentCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 20,
    gap: 12,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  consentTitle: { fontSize: 18, fontWeight: "700" },
  consentHint: { fontSize: 14, color: "#52525b" },
  consentDocLink: { fontSize: 14, color: "#000", textDecorationLine: "underline" },
  consentButton: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    marginTop: 8,
  },
  consentButtonDisabled: { opacity: 0.6 },
  consentButtonText: { color: "#fff", fontWeight: "600" },
  consentLogoutLink: { fontSize: 14, color: "#71717a", textDecorationLine: "underline", textAlign: "center" },
});

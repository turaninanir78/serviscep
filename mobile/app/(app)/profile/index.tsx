import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { User } from "@/lib/types";

type EmailStep = { name: "view" } | { name: "enter-email" } | { name: "enter-code"; email: string };

export default function ProfileScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [step, setStep] = useState<EmailStep>({ name: "view" });
  const [emailInput, setEmailInput] = useState("");
  const [code, setCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  async function handleRequestOtp() {
    setFormError(null);
    setSubmitting(true);
    try {
      await api.requestAddEmailOtp(emailInput);
      setStep({ name: "enter-code", email: emailInput });
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyCode() {
    if (step.name !== "enter-code") return;
    setFormError(null);
    setSubmitting(true);
    try {
      const updated = await api.verifyAddEmail(step.email, code);
      setUser(updated);
      setStep({ name: "view" });
      setCode("");
      setEmailInput("");
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.screen}>
      <NavRow active="profile" />
      <View style={styles.container}>
        {loadError && (
          <Text style={styles.error} testID="profile-error">
            {loadError}
          </Text>
        )}

        {!loadError && !user && <ActivityIndicator testID="profile-loading" />}

        {user && (
          <>
            <View style={styles.card}>
              <View style={styles.row}>
                <Text style={styles.label}>Telefon</Text>
                <Text style={styles.value} testID="profile-phone">
                  {user.phone ?? "—"}
                </Text>
              </View>
              <View style={styles.row}>
                <Text style={styles.label}>E-posta</Text>
                <Text style={styles.value} testID="profile-email">
                  {user.email ?? "Eklenmemiş"}
                </Text>
              </View>
            </View>

            {user.email === null && step.name === "view" && (
              <Pressable
                style={styles.button}
                onPress={() => setStep({ name: "enter-email" })}
                testID="profile-add-email"
              >
                <Text style={styles.buttonText}>E-posta Ekle</Text>
              </Pressable>
            )}

            {step.name === "enter-email" && (
              <View style={styles.card}>
                <TextInput
                  style={styles.input}
                  placeholder="E-posta Adresi"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  value={emailInput}
                  onChangeText={setEmailInput}
                  testID="profile-email-input"
                />
                {formError && (
                  <Text style={styles.error} testID="profile-form-error">
                    {formError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, submitting && styles.buttonDisabled]}
                  onPress={handleRequestOtp}
                  disabled={submitting}
                  testID="profile-request-otp"
                >
                  {submitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Kod Gönder</Text>
                  )}
                </Pressable>
              </View>
            )}

            {step.name === "enter-code" && (
              <View style={styles.card}>
                <Text style={styles.hint}>{step.email} adresine gönderilen kodu girin.</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Doğrulama Kodu"
                  keyboardType="number-pad"
                  value={code}
                  onChangeText={setCode}
                  testID="profile-otp-code"
                />
                {formError && (
                  <Text style={styles.error} testID="profile-form-error">
                    {formError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, submitting && styles.buttonDisabled]}
                  onPress={handleVerifyCode}
                  disabled={submitting}
                  testID="profile-verify-otp"
                >
                  {submitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Doğrula</Text>
                  )}
                </Pressable>
              </View>
            )}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  container: { flex: 1, padding: 16, gap: 12 },
  card: {
    borderWidth: 1,
    borderColor: "#e4e4e7",
    borderRadius: 8,
    padding: 12,
    gap: 10,
  },
  row: { flexDirection: "row", justifyContent: "space-between" },
  label: { color: "#71717a", fontSize: 14 },
  value: { color: "#000", fontSize: 14, fontWeight: "500" },
  hint: { fontSize: 14, color: "#52525b" },
  input: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  button: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  error: { color: "#dc2626" },
});

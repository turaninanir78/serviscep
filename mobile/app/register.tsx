import { Link, router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api } from "@/lib/api";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { useAuth } from "@/lib/auth-context";
import { describeApiError } from "@/lib/errors";

type Step =
  | { name: "phone" }
  | { name: "otp"; countryCode: string; phoneNumber: string }
  | { name: "password"; countryCode: string; phoneNumber: string; registrationToken: string };

export default function RegisterScreen() {
  const { completeRegistration } = useAuth();
  const [step, setStep] = useState<Step>({ name: "phone" });
  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleRequestOtp() {
    setError(null);
    setSubmitting(true);
    try {
      await api.requestRegisterOtp(countryCode, phoneNumber);
      setStep({ name: "otp", countryCode, phoneNumber });
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyOtp() {
    if (step.name !== "otp") return;
    setError(null);
    setSubmitting(true);
    try {
      const { registration_token } = await api.verifyRegisterOtp(
        step.countryCode,
        step.phoneNumber,
        code,
      );
      setStep({
        name: "password",
        countryCode: step.countryCode,
        phoneNumber: step.phoneNumber,
        registrationToken: registration_token,
      });
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResendOtp() {
    if (step.name !== "otp") return;
    setError(null);
    try {
      await api.requestRegisterOtp(step.countryCode, step.phoneNumber);
    } catch (err) {
      setError(describeApiError(err));
    }
  }

  async function handleComplete() {
    if (step.name !== "password") return;
    setError(null);
    setSubmitting(true);
    try {
      await completeRegistration(step.registrationToken, tenantName, password);
      router.replace("/(app)/appointments");
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Firma Kaydı</Text>

      {step.name === "phone" && (
        <>
          <View style={styles.phoneRow}>
            <View style={styles.countryPicker} testID="register-country-code">
              {COUNTRY_CODES.map((c) => (
                <Text key={c.code} style={styles.countryPickerText}>
                  {c.flag} {c.code}
                </Text>
              ))}
            </View>
            <TextInput
              style={[styles.input, styles.phoneInput]}
              placeholder="5XX XXX XX XX"
              keyboardType="phone-pad"
              value={phoneNumber}
              onChangeText={setPhoneNumber}
              testID="register-phone"
            />
          </View>

          {error && (
            <Text style={styles.error} testID="register-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleRequestOtp}
            disabled={submitting}
            testID="register-request-otp"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Kod Gönder</Text>
            )}
          </Pressable>
        </>
      )}

      {step.name === "otp" && (
        <>
          <Text style={styles.hint}>
            {step.countryCode} {step.phoneNumber} numarasına gönderilen kodu girin.
          </Text>
          <TextInput
            style={styles.input}
            placeholder="Doğrulama Kodu"
            keyboardType="number-pad"
            value={code}
            onChangeText={setCode}
            testID="register-otp-code"
          />

          {error && (
            <Text style={styles.error} testID="register-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleVerifyOtp}
            disabled={submitting}
            testID="register-verify-otp"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Doğrula</Text>
            )}
          </Pressable>

          <Pressable onPress={handleResendOtp} testID="register-resend-otp">
            <Text style={styles.link}>Kodu tekrar gönder</Text>
          </Pressable>
        </>
      )}

      {step.name === "password" && (
        <>
          <TextInput
            style={styles.input}
            placeholder="Firma Adı"
            value={tenantName}
            onChangeText={setTenantName}
            testID="register-tenant-name"
          />
          <TextInput
            style={styles.input}
            placeholder="Şifre"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            testID="register-password"
          />

          {error && (
            <Text style={styles.error} testID="register-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleComplete}
            disabled={submitting}
            testID="register-submit"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Kayıt Ol</Text>
            )}
          </Pressable>
        </>
      )}

      <Link href="/login" style={styles.link}>
        Zaten hesabınız var mı? Giriş yapın
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 24, fontWeight: "700", marginBottom: 16, textAlign: "center" },
  hint: { fontSize: 14, color: "#52525b" },
  phoneRow: { flexDirection: "row", gap: 8 },
  countryPicker: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    justifyContent: "center",
  },
  countryPickerText: { fontSize: 16 },
  phoneInput: { flex: 1 },
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
    padding: 14,
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  error: { color: "#dc2626" },
  link: { textAlign: "center", marginTop: 16, color: "#000", textDecorationLine: "underline" },
});

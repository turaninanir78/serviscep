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
import { describeApiError } from "@/lib/errors";

type Channel = "sms" | "email";

type Step =
  | { name: "phone" }
  | { name: "channel"; countryCode: string; phoneNumber: string }
  | { name: "otp"; countryCode: string; phoneNumber: string; channel: Channel | null }
  | { name: "password"; resetToken: string }
  | { name: "done" };

export default function ForgotPasswordScreen() {
  const [step, setStep] = useState<Step>({ name: "phone" });
  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleRequestOtp() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.requestPasswordResetOtp(countryCode, phoneNumber);
      if (res.channel_choice_required) {
        setStep({ name: "channel", countryCode, phoneNumber });
      } else {
        setStep({ name: "otp", countryCode, phoneNumber, channel: null });
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePickChannel(channel: Channel) {
    if (step.name !== "channel") return;
    setError(null);
    setSubmitting(true);
    try {
      await api.requestPasswordResetOtp(step.countryCode, step.phoneNumber, channel);
      setStep({ name: "otp", countryCode: step.countryCode, phoneNumber: step.phoneNumber, channel });
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
      const { reset_token } = await api.verifyPasswordResetOtp(
        step.countryCode,
        step.phoneNumber,
        code,
      );
      setStep({ name: "password", resetToken: reset_token });
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
      await api.requestPasswordResetOtp(
        step.countryCode,
        step.phoneNumber,
        step.channel ?? undefined,
      );
    } catch (err) {
      setError(describeApiError(err));
    }
  }

  async function handleComplete() {
    if (step.name !== "password") return;
    setError(null);
    setSubmitting(true);
    try {
      await api.completePasswordReset(step.resetToken, newPassword);
      setStep({ name: "done" });
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Şifremi Unuttum</Text>

      {step.name === "phone" && (
        <>
          <View style={styles.phoneRow}>
            <View style={styles.countryPicker} testID="forgot-password-country-code">
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
              testID="forgot-password-phone"
            />
          </View>

          {error && (
            <Text style={styles.error} testID="forgot-password-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleRequestOtp}
            disabled={submitting}
            testID="forgot-password-request-otp"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Devam Et</Text>
            )}
          </Pressable>
        </>
      )}

      {step.name === "channel" && (
        <>
          <Text style={styles.hint}>Doğrulama kodunu nereye göndermek istersiniz?</Text>

          {error && (
            <Text style={styles.error} testID="forgot-password-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={() => handlePickChannel("sms")}
            disabled={submitting}
            testID="forgot-password-channel-sms"
          >
            <Text style={styles.buttonText}>SMS ile Gönder</Text>
          </Pressable>
          <Pressable
            style={[styles.secondaryButton, submitting && styles.buttonDisabled]}
            onPress={() => handlePickChannel("email")}
            disabled={submitting}
            testID="forgot-password-channel-email"
          >
            <Text style={styles.secondaryButtonText}>E-posta ile Gönder</Text>
          </Pressable>
        </>
      )}

      {step.name === "otp" && (
        <>
          <Text style={styles.hint}>
            {step.channel === "email"
              ? "E-postanıza gönderilen kodu girin."
              : `${step.countryCode} ${step.phoneNumber} numarasına gönderilen kodu girin.`}
          </Text>
          <TextInput
            style={styles.input}
            placeholder="Doğrulama Kodu"
            keyboardType="number-pad"
            value={code}
            onChangeText={setCode}
            testID="forgot-password-otp-code"
          />

          {error && (
            <Text style={styles.error} testID="forgot-password-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleVerifyOtp}
            disabled={submitting}
            testID="forgot-password-verify-otp"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Doğrula</Text>
            )}
          </Pressable>

          <Pressable onPress={handleResendOtp} testID="forgot-password-resend-otp">
            <Text style={styles.link}>Kodu tekrar gönder</Text>
          </Pressable>
        </>
      )}

      {step.name === "password" && (
        <>
          <TextInput
            style={styles.input}
            placeholder="Yeni Şifre"
            secureTextEntry
            value={newPassword}
            onChangeText={setNewPassword}
            testID="forgot-password-new-password"
          />
          <Text style={styles.passwordHint}>
            En az 6 karakter, 1 büyük harf, 1 küçük harf ve 1 özel karakter içermeli.
          </Text>

          {error && (
            <Text style={styles.error} testID="forgot-password-error">
              {error}
            </Text>
          )}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={handleComplete}
            disabled={submitting}
            testID="forgot-password-submit"
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Şifreyi Güncelle</Text>
            )}
          </Pressable>
        </>
      )}

      {step.name === "done" && (
        <>
          <Text style={styles.hint}>Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.</Text>
          <Pressable
            style={styles.button}
            onPress={() => router.replace("/login")}
            testID="forgot-password-go-to-login"
          >
            <Text style={styles.buttonText}>Giriş Yap</Text>
          </Pressable>
        </>
      )}

      {step.name !== "done" && (
        <Link href="/login" style={styles.link}>
          Giriş ekranına dön
        </Link>
      )}
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
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  secondaryButtonText: { color: "#000", fontWeight: "600", fontSize: 16 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  error: { color: "#dc2626" },
  link: { textAlign: "center", marginTop: 16, color: "#000", textDecorationLine: "underline" },
  passwordHint: { fontSize: 12, color: "#71717a" },
});

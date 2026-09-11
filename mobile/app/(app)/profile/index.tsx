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
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";
import type { User } from "@/lib/types";

const PASSWORD_HINT =
  "En az 6 karakter, 1 büyük harf, 1 küçük harf ve 1 özel karakter içermeli.";

type EmailStep = { name: "closed" } | { name: "enter-email" } | { name: "enter-code"; email: string };
type PhoneStep =
  | { name: "closed" }
  | { name: "enter-phone" }
  | { name: "enter-code"; countryCode: string; phoneNumber: string };
type PasswordStep = { name: "closed" } | { name: "open" };

export default function ProfileScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [emailStep, setEmailStep] = useState<EmailStep>({ name: "closed" });
  const [emailInput, setEmailInput] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailSubmitting, setEmailSubmitting] = useState(false);

  const [phoneStep, setPhoneStep] = useState<PhoneStep>({ name: "closed" });
  const [phoneNumberInput, setPhoneNumberInput] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSubmitting, setPhoneSubmitting] = useState(false);

  const [passwordStep, setPasswordStep] = useState<PasswordStep>({ name: "closed" });
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  async function handleRequestEmailOtp() {
    setEmailError(null);
    setEmailSubmitting(true);
    try {
      await api.requestAddEmailOtp(emailInput);
      setEmailStep({ name: "enter-code", email: emailInput });
    } catch (err) {
      setEmailError(describeApiError(err));
    } finally {
      setEmailSubmitting(false);
    }
  }

  async function handleVerifyEmailCode() {
    if (emailStep.name !== "enter-code") return;
    setEmailError(null);
    setEmailSubmitting(true);
    try {
      const updated = await api.verifyAddEmail(emailStep.email, emailCode);
      setUser(updated);
      setEmailStep({ name: "closed" });
      setEmailCode("");
      setEmailInput("");
    } catch (err) {
      setEmailError(describeApiError(err));
    } finally {
      setEmailSubmitting(false);
    }
  }

  async function handleRequestPhoneOtp() {
    setPhoneError(null);
    setPhoneSubmitting(true);
    try {
      await api.requestChangePhoneOtp(DEFAULT_COUNTRY_CODE, phoneNumberInput);
      setPhoneStep({
        name: "enter-code",
        countryCode: DEFAULT_COUNTRY_CODE,
        phoneNumber: phoneNumberInput,
      });
    } catch (err) {
      setPhoneError(describeApiError(err));
    } finally {
      setPhoneSubmitting(false);
    }
  }

  async function handleVerifyPhoneCode() {
    if (phoneStep.name !== "enter-code") return;
    setPhoneError(null);
    setPhoneSubmitting(true);
    try {
      const updated = await api.verifyChangePhoneOtp(
        phoneStep.countryCode,
        phoneStep.phoneNumber,
        phoneCode,
      );
      setUser(updated);
      setPhoneStep({ name: "closed" });
      setPhoneCode("");
      setPhoneNumberInput("");
    } catch (err) {
      setPhoneError(describeApiError(err));
    } finally {
      setPhoneSubmitting(false);
    }
  }

  async function handleChangePassword() {
    setPasswordError(null);
    setPasswordSuccess(false);
    setPasswordSubmitting(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordStep({ name: "closed" });
    } catch (err) {
      setPasswordError(describeApiError(err));
    } finally {
      setPasswordSubmitting(false);
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

            {passwordSuccess && (
              <Text style={styles.success} testID="profile-password-success">
                Şifreniz güncellendi.
              </Text>
            )}

            {/* --- E-posta --- */}
            {emailStep.name === "closed" && (
              <Pressable
                style={styles.button}
                onPress={() => setEmailStep({ name: "enter-email" })}
                testID="profile-add-email"
              >
                <Text style={styles.buttonText}>
                  {user.email === null ? "E-posta Ekle" : "E-postamı Değiştir"}
                </Text>
              </Pressable>
            )}

            {emailStep.name === "enter-email" && (
              <View style={styles.card}>
                <TextInput
                  style={styles.input}
                  placeholder="Yeni E-posta Adresi"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  value={emailInput}
                  onChangeText={setEmailInput}
                  testID="profile-email-input"
                />
                {emailError && (
                  <Text style={styles.error} testID="profile-email-error">
                    {emailError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, emailSubmitting && styles.buttonDisabled]}
                  onPress={handleRequestEmailOtp}
                  disabled={emailSubmitting}
                  testID="profile-request-email-otp"
                >
                  {emailSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Kod Gönder</Text>
                  )}
                </Pressable>
              </View>
            )}

            {emailStep.name === "enter-code" && (
              <View style={styles.card}>
                <Text style={styles.hint}>{emailStep.email} adresine gönderilen kodu girin.</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Doğrulama Kodu"
                  keyboardType="number-pad"
                  value={emailCode}
                  onChangeText={setEmailCode}
                  testID="profile-email-otp-code"
                />
                {emailError && (
                  <Text style={styles.error} testID="profile-email-error">
                    {emailError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, emailSubmitting && styles.buttonDisabled]}
                  onPress={handleVerifyEmailCode}
                  disabled={emailSubmitting}
                  testID="profile-verify-email-otp"
                >
                  {emailSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Doğrula</Text>
                  )}
                </Pressable>
              </View>
            )}

            {/* --- Telefon --- */}
            {phoneStep.name === "closed" && (
              <Pressable
                style={styles.secondaryButton}
                onPress={() => setPhoneStep({ name: "enter-phone" })}
                testID="profile-change-phone"
              >
                <Text style={styles.secondaryButtonText}>Telefon Numaramı Değiştir</Text>
              </Pressable>
            )}

            {phoneStep.name === "enter-phone" && (
              <View style={styles.card}>
                <View style={styles.phoneRow}>
                  <View style={styles.countryPicker}>
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
                    value={phoneNumberInput}
                    onChangeText={setPhoneNumberInput}
                    testID="profile-phone-input"
                  />
                </View>
                {phoneError && (
                  <Text style={styles.error} testID="profile-phone-error">
                    {phoneError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, phoneSubmitting && styles.buttonDisabled]}
                  onPress={handleRequestPhoneOtp}
                  disabled={phoneSubmitting}
                  testID="profile-request-phone-otp"
                >
                  {phoneSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Kod Gönder</Text>
                  )}
                </Pressable>
              </View>
            )}

            {phoneStep.name === "enter-code" && (
              <View style={styles.card}>
                <Text style={styles.hint}>
                  {phoneStep.countryCode} {phoneStep.phoneNumber} numarasına gönderilen kodu
                  girin.
                </Text>
                <TextInput
                  style={styles.input}
                  placeholder="Doğrulama Kodu"
                  keyboardType="number-pad"
                  value={phoneCode}
                  onChangeText={setPhoneCode}
                  testID="profile-phone-otp-code"
                />
                {phoneError && (
                  <Text style={styles.error} testID="profile-phone-error">
                    {phoneError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, phoneSubmitting && styles.buttonDisabled]}
                  onPress={handleVerifyPhoneCode}
                  disabled={phoneSubmitting}
                  testID="profile-verify-phone-otp"
                >
                  {phoneSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Doğrula</Text>
                  )}
                </Pressable>
              </View>
            )}

            {/* --- Şifre --- */}
            {passwordStep.name === "closed" && (
              <Pressable
                style={styles.secondaryButton}
                onPress={() => {
                  setPasswordSuccess(false);
                  setPasswordStep({ name: "open" });
                }}
                testID="profile-change-password"
              >
                <Text style={styles.secondaryButtonText}>Şifremi Değiştir</Text>
              </Pressable>
            )}

            {passwordStep.name === "open" && (
              <View style={styles.card}>
                <TextInput
                  style={styles.input}
                  placeholder="Mevcut Şifre"
                  secureTextEntry
                  value={currentPassword}
                  onChangeText={setCurrentPassword}
                  testID="profile-current-password"
                />
                <TextInput
                  style={styles.input}
                  placeholder="Yeni Şifre"
                  secureTextEntry
                  value={newPassword}
                  onChangeText={setNewPassword}
                  testID="profile-new-password"
                />
                <Text style={styles.hint}>{PASSWORD_HINT}</Text>
                {passwordError && (
                  <Text style={styles.error} testID="profile-password-error">
                    {passwordError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, passwordSubmitting && styles.buttonDisabled]}
                  onPress={handleChangePassword}
                  disabled={passwordSubmitting}
                  testID="profile-submit-password"
                >
                  {passwordSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Şifreyi Güncelle</Text>
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
  hint: { fontSize: 12, color: "#52525b" },
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
    padding: 12,
    alignItems: "center",
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  secondaryButtonText: { color: "#3f3f46", fontWeight: "600", fontSize: 14 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  error: { color: "#dc2626" },
  success: { color: "#16a34a" },
});

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

import { useAuth } from "@/lib/auth-context";
import { describeApiError } from "@/lib/errors";

export default function LoginScreen() {
  const { login } = useAuth();
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      await login(emailOrPhone, password);
      router.replace("/(app)/appointments");
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>ServisCep</Text>

      <TextInput
        style={styles.input}
        placeholder="E-posta veya Telefon"
        autoCapitalize="none"
        autoCorrect={false}
        value={emailOrPhone}
        onChangeText={setEmailOrPhone}
        testID="login-identifier"
      />
      <TextInput
        style={styles.input}
        placeholder="Şifre"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        testID="login-password"
      />
      <Link href="/forgot-password" style={styles.forgotPasswordLink}>
        Şifremi unuttum
      </Link>

      {error && (
        <Text style={styles.error} testID="login-error">
          {error}
        </Text>
      )}

      <Pressable
        style={[styles.button, submitting && styles.buttonDisabled]}
        onPress={handleSubmit}
        disabled={submitting}
        testID="login-submit"
      >
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Giriş Yap</Text>
        )}
      </Pressable>

      <Link href="/register" style={styles.link}>
        Hesabınız yok mu? Kayıt olun
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 28, fontWeight: "700", marginBottom: 16, textAlign: "center" },
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
  forgotPasswordLink: {
    textAlign: "right",
    fontSize: 12,
    color: "#71717a",
    textDecorationLine: "underline",
  },
});

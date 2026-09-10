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

export default function RegisterScreen() {
  const { register } = useAuth();
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      await register(tenantName, email, password);
      router.replace("/(app)/appointments");
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Firma Kaydı</Text>

      <TextInput
        style={styles.input}
        placeholder="Firma Adı"
        value={tenantName}
        onChangeText={setTenantName}
        testID="register-tenant-name"
      />
      <TextInput
        style={styles.input}
        placeholder="E-posta"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        testID="register-email"
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
        onPress={handleSubmit}
        disabled={submitting}
        testID="register-submit"
      >
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Kayıt Ol</Text>
        )}
      </Pressable>

      <Link href="/login" style={styles.link}>
        Zaten hesabınız var mı? Giriş yapın
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 24, fontWeight: "700", marginBottom: 16, textAlign: "center" },
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

import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { Customer } from "@/lib/types";

// Hem yeni-randevu ekranindaki "hizli musteri ekle" akisi hem de musteri
// listesi ekraninin kendi "yeni musteri" formu ayni ad+telefon+POST
// /customers mantigini kullaniyor - kod tekrarini onlemek icin tek bir
// yerde tutuluyor.
interface QuickCustomerFormProps {
  onCreated: (customer: Customer) => void;
}

export function QuickCustomerForm({ onCreated }: QuickCustomerFormProps) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!phone.trim()) return;

    setError(null);
    setSubmitting(true);
    try {
      const customer = await api.createCustomer({
        whatsapp_number: phone.trim(),
        display_name: name.trim() || null,
      });
      setName("");
      setPhone("");
      onCreated(customer);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.form}>
      <TextInput
        testID="new-customer-name"
        placeholder="Ad (opsiyonel)"
        value={name}
        onChangeText={setName}
        style={styles.input}
      />
      <TextInput
        testID="new-customer-phone"
        placeholder="WhatsApp numarası"
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
        style={styles.input}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable
        testID="new-customer-submit"
        style={[styles.button, (!phone.trim() || submitting) && styles.buttonDisabled]}
        disabled={!phone.trim() || submitting}
        onPress={handleSubmit}
      >
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Müşteriyi Ekle</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  error: { color: "#dc2626" },
  button: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontWeight: "600" },
});

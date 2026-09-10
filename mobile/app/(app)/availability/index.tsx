import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { AvailabilityRule, StaffMember } from "@/lib/types";

const WEEKDAY_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

// Native bir time-picker modulu eklemek yerine (Expo Go uyumluluk riski,
// mobil app foundation gorevinde de kacinilan pattern), diger ekranlardaki
// gibi basit, platformdan bagimsiz bir metin girisi kullaniyoruz.
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

function validateTimes(start: string, end: string): string | null {
  if (!TIME_PATTERN.test(start) || !TIME_PATTERN.test(end)) {
    return "Saat SS:DD formatında olmalı (ör. 09:00).";
  }
  // Backend zaten CHECK ile reddediyor (bkz. web'in AvailabilityPage'i), ama
  // API hatasi beklemeden aninda geri bildirim vermek daha iyi bir deneyim.
  if (start >= end) {
    return "Bitiş saati başlangıç saatinden sonra olmalı.";
  }
  return null;
}

export default function AvailabilityScreen() {
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [rules, setRules] = useState<AvailabilityRule[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedStaffId, setSelectedStaffId] = useState<number | null>(null);

  const [weekday, setWeekday] = useState(0);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editWeekday, setEditWeekday] = useState(0);
  const [editStartTime, setEditStartTime] = useState("");
  const [editEndTime, setEditEndTime] = useState("");
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoadError(null);
    Promise.all([api.getStaffMembers(), api.getAvailabilityRules()])
      .then(([staffData, rulesData]) => {
        setStaffMembers(staffData);
        setRules(rulesData);
        // Ilk yuklemede otomatik ilk personeli sec - sonraki yenilemelerde
        // (odak/kaydet sonrasi) kullanicinin secimini korumak icin sadece
        // henuz secim yoksa ata.
        setSelectedStaffId((prev) => prev ?? (staffData.length > 0 ? staffData[0].id : null));
      })
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function handleAddRule() {
    if (!selectedStaffId) return;
    const validationError = validateTimes(startTime, endTime);
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setFormError(null);
    setSubmitting(true);
    try {
      await api.createAvailabilityRule({
        staff_id: selectedStaffId,
        weekday,
        start_time: startTime,
        end_time: endTime,
      });
      setStartTime("");
      setEndTime("");
      load();
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(rule: AvailabilityRule) {
    setEditingId(rule.id);
    setEditWeekday(rule.weekday);
    setEditStartTime(rule.start_time.slice(0, 5));
    setEditEndTime(rule.end_time.slice(0, 5));
    setEditError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditError(null);
  }

  async function handleSaveEdit(id: number) {
    const validationError = validateTimes(editStartTime, editEndTime);
    if (validationError) {
      setEditError(validationError);
      return;
    }

    setEditError(null);
    setEditSubmitting(true);
    try {
      await api.updateAvailabilityRule(id, {
        weekday: editWeekday,
        start_time: editStartTime,
        end_time: editEndTime,
      });
      setEditingId(null);
      load();
    } catch (err) {
      setEditError(describeApiError(err));
    } finally {
      setEditSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{loadError}</Text>
      </View>
    );
  }

  const visibleRules = rules?.filter((r) => r.staff_id === selectedStaffId) ?? [];

  return (
    <View style={styles.container}>
      <NavRow active="availability" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        {staffMembers.length === 0 ? (
          <Text style={styles.detailLine}>
            Müsaitlik eklemeden önce en az bir personel oluşturmalısınız.
          </Text>
        ) : (
          <>
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Personel</Text>
              <View style={styles.chipRow}>
                {staffMembers.map((staff) => (
                  <Pressable
                    key={staff.id}
                    testID={`staff-filter-${staff.id}`}
                    onPress={() => setSelectedStaffId(staff.id)}
                    style={[styles.chip, selectedStaffId === staff.id && styles.chipActive]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        selectedStaffId === staff.id && styles.chipTextActive,
                      ]}
                    >
                      {staff.name}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Çalışma Saatleri</Text>
              {rules === null ? (
                <ActivityIndicator style={{ marginTop: 8 }} />
              ) : visibleRules.length === 0 ? (
                <Text style={styles.detailLine}>Bu personel için henüz çalışma saati yok.</Text>
              ) : (
                visibleRules.map((rule) => (
                  <View key={rule.id} testID={`rule-row-${rule.id}`} style={styles.ruleRow}>
                    {editingId === rule.id ? (
                      <View style={{ gap: 8, flex: 1 }}>
                        <View style={styles.chipRow}>
                          {WEEKDAY_LABELS.map((label, index) => (
                            <Pressable
                              key={index}
                              testID={`edit-weekday-${rule.id}-${index}`}
                              onPress={() => setEditWeekday(index)}
                              style={[styles.chipSmall, editWeekday === index && styles.chipActive]}
                            >
                              <Text
                                style={[
                                  styles.chipText,
                                  editWeekday === index && styles.chipTextActive,
                                ]}
                              >
                                {label.slice(0, 3)}
                              </Text>
                            </Pressable>
                          ))}
                        </View>
                        <View style={{ flexDirection: "row", gap: 8 }}>
                          <TextInput
                            testID={`edit-start-${rule.id}`}
                            value={editStartTime}
                            onChangeText={setEditStartTime}
                            placeholder="09:00"
                            style={styles.timeInput}
                          />
                          <TextInput
                            testID={`edit-end-${rule.id}`}
                            value={editEndTime}
                            onChangeText={setEditEndTime}
                            placeholder="18:00"
                            style={styles.timeInput}
                          />
                        </View>
                        {editError && <Text style={styles.error}>{editError}</Text>}
                        <View style={{ flexDirection: "row", gap: 16, alignItems: "center" }}>
                          <Pressable
                            testID={`save-edit-${rule.id}`}
                            onPress={() => handleSaveEdit(rule.id)}
                            disabled={editSubmitting}
                            style={[styles.smallButton, editSubmitting && styles.buttonDisabled]}
                          >
                            {editSubmitting ? (
                              <ActivityIndicator color="#fff" size="small" />
                            ) : (
                              <Text style={styles.smallButtonText}>Kaydet</Text>
                            )}
                          </Pressable>
                          <Pressable testID={`cancel-edit-${rule.id}`} onPress={cancelEdit}>
                            <Text style={styles.link}>Vazgeç</Text>
                          </Pressable>
                        </View>
                      </View>
                    ) : (
                      <>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.detailLine}>
                            {WEEKDAY_LABELS[rule.weekday] ?? rule.weekday}{" "}
                            {rule.start_time.slice(0, 5)}–{rule.end_time.slice(0, 5)}
                          </Text>
                        </View>
                        <Pressable testID={`edit-rule-${rule.id}`} onPress={() => startEdit(rule)}>
                          <Text style={styles.link}>Düzenle</Text>
                        </Pressable>
                      </>
                    )}
                  </View>
                ))
              )}
            </View>

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Yeni Çalışma Saati Ekle</Text>
              <View style={styles.chipRow}>
                {WEEKDAY_LABELS.map((label, index) => (
                  <Pressable
                    key={index}
                    testID={`weekday-chip-${index}`}
                    onPress={() => setWeekday(index)}
                    style={[styles.chip, weekday === index && styles.chipActive]}
                  >
                    <Text style={[styles.chipText, weekday === index && styles.chipTextActive]}>
                      {label}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <TextInput
                  testID="start-time-input"
                  value={startTime}
                  onChangeText={setStartTime}
                  placeholder="Başlangıç (09:00)"
                  style={styles.timeInput}
                />
                <TextInput
                  testID="end-time-input"
                  value={endTime}
                  onChangeText={setEndTime}
                  placeholder="Bitiş (18:00)"
                  style={styles.timeInput}
                />
              </View>
              {formError && <Text style={styles.error}>{formError}</Text>}
              <Pressable
                testID="add-rule-submit"
                onPress={handleAddRule}
                disabled={submitting || !startTime || !endTime}
                style={[
                  styles.saveButton,
                  (submitting || !startTime || !endTime) && styles.buttonDisabled,
                ]}
              >
                {submitting ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.buttonText}>Ekle</Text>
                )}
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafafa" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    gap: 10,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  sectionTitle: { fontSize: 14, fontWeight: "700" },
  detailLine: { fontSize: 14, color: "#3f3f46" },
  error: { color: "#dc2626" },
  link: { color: "#71717a", textDecorationLine: "underline" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSmall: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: "#000", borderColor: "#000" },
  chipText: { fontSize: 13, color: "#000" },
  chipTextActive: { color: "#fff" },
  ruleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#f4f4f5",
  },
  timeInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  saveButton: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  smallButton: {
    backgroundColor: "#000",
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignItems: "center",
  },
  smallButtonText: { color: "#fff", fontWeight: "600", fontSize: 13 },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontWeight: "600" },
});

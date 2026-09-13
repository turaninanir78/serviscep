import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { AvailabilityOverride, AvailabilityRule, ScheduleMode, StaffMember, Tenant } from "@/lib/types";

const WEEKDAY_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

// Native bir time/date-picker modulu eklemek yerine (Expo Go uyumluluk riski,
// mobil app foundation gorevinde de kacinilan pattern), diger ekranlardaki
// gibi basit, platformdan bagimsiz bir metin girisi kullaniyoruz.
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

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

function modeLabel(rule: { mode: ScheduleMode; slot_duration_minutes: number | null; gap_minutes: number }): string {
  return rule.mode === "standard"
    ? `Standart (${rule.slot_duration_minutes} dk + ${rule.gap_minutes} dk boşluk)`
    : "Esnek";
}

function ModeFields({
  idPrefix,
  mode,
  setMode,
  slotDuration,
  setSlotDuration,
  gapMinutes,
  setGapMinutes,
}: {
  idPrefix: string;
  mode: ScheduleMode;
  setMode: (m: ScheduleMode) => void;
  slotDuration: string;
  setSlotDuration: (v: string) => void;
  gapMinutes: string;
  setGapMinutes: (v: string) => void;
}) {
  return (
    <View style={{ gap: 8 }}>
      <View style={styles.chipRow}>
        <Pressable
          testID={`${idPrefix}-mode-flexible`}
          onPress={() => setMode("flexible")}
          style={[styles.chip, mode === "flexible" && styles.chipActive]}
        >
          <Text style={[styles.chipText, mode === "flexible" && styles.chipTextActive]}>
            Esnek (hizmet süresine göre)
          </Text>
        </Pressable>
        <Pressable
          testID={`${idPrefix}-mode-standard`}
          onPress={() => setMode("standard")}
          style={[styles.chip, mode === "standard" && styles.chipActive]}
        >
          <Text style={[styles.chipText, mode === "standard" && styles.chipTextActive]}>
            Standart (sabit randevu izgarası)
          </Text>
        </Pressable>
      </View>
      {mode === "standard" && (
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TextInput
            testID={`${idPrefix}-slot-duration`}
            value={slotDuration}
            onChangeText={setSlotDuration}
            placeholder="Randevu süresi (dk)"
            keyboardType="number-pad"
            style={styles.timeInput}
          />
          <TextInput
            testID={`${idPrefix}-gap-minutes`}
            value={gapMinutes}
            onChangeText={setGapMinutes}
            placeholder="Boşluk (dk)"
            keyboardType="number-pad"
            style={styles.timeInput}
          />
        </View>
      )}
    </View>
  );
}

export default function AvailabilityScreen() {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [rules, setRules] = useState<AvailabilityRule[] | null>(null);
  const [overrides, setOverrides] = useState<AvailabilityOverride[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedStaffId, setSelectedStaffId] = useState<number | null>(null);

  const isOwner = tenant === null || tenant.my_role === "owner";

  const [weekday, setWeekday] = useState(0);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [mode, setMode] = useState<ScheduleMode>("flexible");
  const [slotDuration, setSlotDuration] = useState("60");
  const [gapMinutes, setGapMinutes] = useState("0");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editWeekday, setEditWeekday] = useState(0);
  const [editStartTime, setEditStartTime] = useState("");
  const [editEndTime, setEditEndTime] = useState("");
  const [editMode, setEditMode] = useState<ScheduleMode>("flexible");
  const [editSlotDuration, setEditSlotDuration] = useState("60");
  const [editGapMinutes, setEditGapMinutes] = useState("0");
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // --- Tarihe özel istisna ---
  const [overrideDate, setOverrideDate] = useState("");
  const [overrideStart, setOverrideStart] = useState("");
  const [overrideEnd, setOverrideEnd] = useState("");
  const [overrideMode, setOverrideMode] = useState<ScheduleMode>("flexible");
  const [overrideSlotDuration, setOverrideSlotDuration] = useState("60");
  const [overrideGapMinutes, setOverrideGapMinutes] = useState("0");
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  // --- Randevu açık kalma süresi ---
  const [horizonUnlimited, setHorizonUnlimited] = useState(true);
  const [horizonDays, setHorizonDays] = useState("7");
  const [horizonSaving, setHorizonSaving] = useState(false);
  const [horizonError, setHorizonError] = useState<string | null>(null);
  const [horizonSaved, setHorizonSaved] = useState(false);

  const load = useCallback(() => {
    setLoadError(null);
    Promise.all([api.getStaffMembers(), api.getAvailabilityRules(), api.getAvailabilityOverrides()])
      .then(([staffData, rulesData, overridesData]) => {
        setStaffMembers(staffData);
        setRules(rulesData);
        setOverrides(overridesData);
        // Ilk yuklemede otomatik ilk personeli sec - sonraki yenilemelerde
        // (odak/kaydet sonrasi) kullanicinin secimini korumak icin sadece
        // henuz secim yoksa ata.
        setSelectedStaffId((prev) => prev ?? (staffData.length > 0 ? staffData[0].id : null));
      })
      .catch((err) => setLoadError(describeApiError(err)));
    api
      .getMyTenant()
      .then((t) => {
        setTenant(t);
        if (t.my_role === "staff" && t.my_staff_member_id !== null) {
          setSelectedStaffId(t.my_staff_member_id);
        }
        setHorizonUnlimited(t.max_advance_booking_days === null);
        if (t.max_advance_booking_days !== null) {
          setHorizonDays(String(t.max_advance_booking_days));
        }
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
    if (mode === "standard" && !slotDuration) {
      setFormError("Standart modda randevu süresi zorunlu.");
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
        mode,
        slot_duration_minutes: mode === "standard" ? Number(slotDuration) : null,
        gap_minutes: mode === "standard" ? Number(gapMinutes) : 0,
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
    setEditMode(rule.mode);
    setEditSlotDuration(rule.slot_duration_minutes !== null ? String(rule.slot_duration_minutes) : "60");
    setEditGapMinutes(String(rule.gap_minutes));
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
    if (editMode === "standard" && !editSlotDuration) {
      setEditError("Standart modda randevu süresi zorunlu.");
      return;
    }

    setEditError(null);
    setEditSubmitting(true);
    try {
      await api.updateAvailabilityRule(id, {
        weekday: editWeekday,
        start_time: editStartTime,
        end_time: editEndTime,
        mode: editMode,
        slot_duration_minutes: editMode === "standard" ? Number(editSlotDuration) : null,
        gap_minutes: editMode === "standard" ? Number(editGapMinutes) : 0,
      });
      setEditingId(null);
      load();
    } catch (err) {
      setEditError(describeApiError(err));
    } finally {
      setEditSubmitting(false);
    }
  }

  async function handleCreateOverride(applyToWeeklyTemplate: boolean) {
    setOverrideError(null);

    if (!selectedStaffId) return;
    if (!DATE_PATTERN.test(overrideDate)) {
      setOverrideError("Tarih YYYY-AA-GG formatında olmalı (ör. 2026-11-02).");
      return;
    }
    const validationError = validateTimes(overrideStart, overrideEnd);
    if (validationError) {
      setOverrideError(validationError);
      return;
    }
    if (overrideMode === "standard" && !overrideSlotDuration) {
      setOverrideError("Standart modda randevu süresi zorunlu.");
      return;
    }

    setOverrideSubmitting(true);
    try {
      await api.createAvailabilityOverride({
        staff_id: selectedStaffId,
        date: overrideDate,
        start_time: overrideStart,
        end_time: overrideEnd,
        mode: overrideMode,
        slot_duration_minutes: overrideMode === "standard" ? Number(overrideSlotDuration) : null,
        gap_minutes: overrideMode === "standard" ? Number(overrideGapMinutes) : 0,
        apply_to_weekly_template: applyToWeeklyTemplate,
      });
      setOverrideDate("");
      setOverrideStart("");
      setOverrideEnd("");
      load();
    } catch (err) {
      setOverrideError(describeApiError(err));
    } finally {
      setOverrideSubmitting(false);
    }
  }

  async function handleRemoveOverride(id: number) {
    try {
      await api.removeAvailabilityOverride(id);
      load();
    } catch (err) {
      setOverrideError(describeApiError(err));
    }
  }

  async function handleSaveHorizon() {
    setHorizonError(null);
    setHorizonSaved(false);
    setHorizonSaving(true);
    try {
      const value = horizonUnlimited ? null : Number(horizonDays);
      const updated = await api.updateBookingSettings(value);
      setTenant(updated);
      setHorizonSaved(true);
    } catch (err) {
      setHorizonError(describeApiError(err));
    } finally {
      setHorizonSaving(false);
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
  const visibleOverrides = overrides?.filter((o) => o.staff_id === selectedStaffId) ?? [];

  return (
    <View style={styles.container}>
      <NavRow active="availability" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16 }}>
        {isOwner && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Randevu Açık Kalma Süresi</Text>
            <View style={styles.rowBetween}>
              <Text style={styles.detailLine}>Sınırsız</Text>
              <Switch
                testID="horizon-unlimited-toggle"
                value={horizonUnlimited}
                onValueChange={setHorizonUnlimited}
              />
            </View>
            {!horizonUnlimited && (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Text style={styles.detailLine}>En fazla</Text>
                <TextInput
                  testID="horizon-days-input"
                  value={horizonDays}
                  onChangeText={setHorizonDays}
                  keyboardType="number-pad"
                  style={[styles.timeInput, { flex: 0, width: 80 }]}
                />
                <Text style={styles.detailLine}>gün öncesinden randevu alınabilir</Text>
              </View>
            )}
            {horizonError && <Text style={styles.error}>{horizonError}</Text>}
            {horizonSaved && <Text style={styles.success}>Kaydedildi.</Text>}
            <Pressable
              testID="horizon-save"
              onPress={handleSaveHorizon}
              disabled={horizonSaving}
              style={[styles.saveButton, horizonSaving && styles.buttonDisabled]}
            >
              {horizonSaving ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Kaydet</Text>
              )}
            </Pressable>
          </View>
        )}

        {staffMembers.length === 0 ? (
          <Text style={styles.detailLine}>
            Çalışma planı eklemeden önce en az bir personel oluşturmalısınız.
          </Text>
        ) : (
          <>
            {isOwner ? (
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
            ) : (
              <Text style={styles.detailLine}>Kendi çalışma planınız</Text>
            )}

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Haftalık Plan</Text>
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
                        <ModeFields
                          idPrefix={`edit-${rule.id}`}
                          mode={editMode}
                          setMode={setEditMode}
                          slotDuration={editSlotDuration}
                          setSlotDuration={setEditSlotDuration}
                          gapMinutes={editGapMinutes}
                          setGapMinutes={setEditGapMinutes}
                        />
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
                          <Text style={styles.hint}>{modeLabel(rule)}</Text>
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
              <ModeFields
                idPrefix="rule"
                mode={mode}
                setMode={setMode}
                slotDuration={slotDuration}
                setSlotDuration={setSlotDuration}
                gapMinutes={gapMinutes}
                setGapMinutes={setGapMinutes}
              />
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

            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Tarihe Özel Değişiklik</Text>
              <Text style={styles.hint}>
                Sadece seçtiğiniz tarih için geçerli olur, haftalık planı değiştirmez —
                isterseniz kalıcı da yapabilirsiniz.
              </Text>
              <TextInput
                testID="override-date-input"
                value={overrideDate}
                onChangeText={setOverrideDate}
                placeholder="Tarih (2026-11-02)"
                style={styles.timeInput}
              />
              <View style={{ flexDirection: "row", gap: 8 }}>
                <TextInput
                  testID="override-start-input"
                  value={overrideStart}
                  onChangeText={setOverrideStart}
                  placeholder="Başlangıç (14:00)"
                  style={styles.timeInput}
                />
                <TextInput
                  testID="override-end-input"
                  value={overrideEnd}
                  onChangeText={setOverrideEnd}
                  placeholder="Bitiş (16:00)"
                  style={styles.timeInput}
                />
              </View>
              <ModeFields
                idPrefix="override"
                mode={overrideMode}
                setMode={setOverrideMode}
                slotDuration={overrideSlotDuration}
                setSlotDuration={setOverrideSlotDuration}
                gapMinutes={overrideGapMinutes}
                setGapMinutes={setOverrideGapMinutes}
              />
              {overrideError && <Text style={styles.error}>{overrideError}</Text>}
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                <Pressable
                  testID="override-save-once"
                  onPress={() => handleCreateOverride(false)}
                  disabled={overrideSubmitting}
                  style={[styles.saveButton, overrideSubmitting && styles.buttonDisabled]}
                >
                  {overrideSubmitting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Sadece Bu Tarih İçin Kaydet</Text>
                  )}
                </Pressable>
                <Pressable
                  testID="override-save-permanent"
                  onPress={() => handleCreateOverride(true)}
                  disabled={overrideSubmitting}
                  style={[styles.outlineButton, overrideSubmitting && styles.buttonDisabled]}
                >
                  <Text style={styles.outlineButtonText}>
                    Kalıcı Yap (Bu Günü Her Hafta Böyle Yap)
                  </Text>
                </Pressable>
              </View>

              {visibleOverrides.length > 0 && (
                <View style={{ gap: 6, marginTop: 4 }}>
                  {visibleOverrides.map((override) => (
                    <View key={override.id} testID={`override-row-${override.id}`} style={styles.ruleRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.detailLine}>
                          {override.date} {override.start_time.slice(0, 5)}–
                          {override.end_time.slice(0, 5)}
                        </Text>
                        <Text style={styles.hint}>{modeLabel(override)}</Text>
                      </View>
                      <Pressable
                        testID={`override-remove-${override.id}`}
                        onPress={() => handleRemoveOverride(override.id)}
                      >
                        <Text style={styles.dangerLink}>Kaldır</Text>
                      </Pressable>
                    </View>
                  ))}
                </View>
              )}
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
  hint: { fontSize: 12, color: "#71717a" },
  error: { color: "#dc2626" },
  success: { color: "#16a34a" },
  link: { color: "#71717a", textDecorationLine: "underline" },
  dangerLink: { color: "#dc2626", textDecorationLine: "underline", fontSize: 12 },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
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
  outlineButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  outlineButtonText: { color: "#3f3f46", fontWeight: "600" },
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

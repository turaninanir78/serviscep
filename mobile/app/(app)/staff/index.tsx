import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { NavRow } from "@/components/NavRow";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";
import type {
  StaffInvitation,
  StaffMember,
  StaffMembership,
  StaffPermissionKey,
} from "@/lib/types";

const PERMISSION_LABELS: Record<StaffPermissionKey, string> = {
  can_view_customers: "Müşterileri Görüntüleme",
  can_create_appointments: "Randevu Oluşturma",
  can_cancel_appointments: "Randevu İptal Etme",
  can_confirm_complete_appointments: "Randevu Onaylama / Tamamlama",
  can_manage_availability: "Çalışma Planını Oluşturma / Değiştirme",
  can_manage_services: "Hizmetleri Görüntüleme / Düzenleme",
};

const PERMISSION_KEYS = Object.keys(PERMISSION_LABELS) as StaffPermissionKey[];

const INVITATION_STATUS_LABELS: Record<string, string> = {
  pending: "Beklemede",
  accepted: "Kabul edildi",
  revoked: "İptal edildi / Reddedildi",
  expired: "Süresi doldu",
};

export default function StaffScreen() {
  const { tenantRole } = useAuth();
  const isOwner = tenantRole === "owner";

  const [staffMembers, setStaffMembers] = useState<StaffMember[] | null>(null);
  const [invitations, setInvitations] = useState<StaffInvitation[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [inviteCountryCode, setInviteCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [invitePhone, setInvitePhone] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const [permissionsFor, setPermissionsFor] = useState<StaffMember | null>(null);
  const [membership, setMembership] = useState<StaffMembership | "not-linked" | null>(null);
  const [permissionsError, setPermissionsError] = useState<string | null>(null);
  const [savingPermissions, setSavingPermissions] = useState(false);

  function loadStaffMembers() {
    api
      .getStaffMembers()
      .then(setStaffMembers)
      .catch((err) => setError(describeApiError(err)));
  }

  function loadInvitations() {
    if (!isOwner) return;
    api
      .getSentStaffInvitations()
      .then(setInvitations)
      .catch(() => {
        // owner degilse zaten cagirilmiyor - gecici bir hata olursa
        // sayfanin geri kalanini kilitlemiyoruz.
      });
  }

  useFocusEffect(
    useCallback(() => {
      loadStaffMembers();
      loadInvitations();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOwner]),
  );

  async function handleInvite() {
    setInviteError(null);
    setInviting(true);
    try {
      await api.inviteStaffMember(inviteCountryCode, invitePhone);
      setInvitePhone("");
      loadInvitations();
    } catch (err) {
      setInviteError(describeApiError(err));
    } finally {
      setInviting(false);
    }
  }

  async function handleRevokeInvitation(invitation: StaffInvitation) {
    try {
      await api.revokeStaffInvitation(invitation.id);
      loadInvitations();
    } catch (err) {
      setInviteError(describeApiError(err));
    }
  }

  async function openPermissions(staff: StaffMember) {
    setPermissionsFor(staff);
    setMembership(null);
    setPermissionsError(null);
    try {
      const result = await api.getStaffMembership(staff.id);
      setMembership(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setMembership("not-linked");
      } else {
        setPermissionsError(describeApiError(err));
      }
    }
  }

  function closePermissions() {
    setPermissionsFor(null);
    setMembership(null);
    setPermissionsError(null);
  }

  async function handleTogglePermission(key: StaffPermissionKey) {
    if (membership === null || membership === "not-linked" || permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      const updated = await api.updateStaffPermissions(permissionsFor.id, {
        [key]: !membership[key],
      });
      setMembership(updated);
    } catch (err) {
      setPermissionsError(describeApiError(err));
    } finally {
      setSavingPermissions(false);
    }
  }

  async function handleGrantAll() {
    if (permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      const allTrue = Object.fromEntries(PERMISSION_KEYS.map((key) => [key, true]));
      const updated = await api.updateStaffPermissions(permissionsFor.id, allTrue);
      setMembership(updated);
    } catch (err) {
      setPermissionsError(describeApiError(err));
    } finally {
      setSavingPermissions(false);
    }
  }

  async function handleEndMembership() {
    if (permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      await api.endStaffMembership(permissionsFor.id);
      closePermissions();
      loadStaffMembers();
    } catch (err) {
      setPermissionsError(describeApiError(err));
      setSavingPermissions(false);
    }
  }

  return (
    <View style={styles.container}>
      <NavRow active="staff" />

      <FlatList
        data={staffMembers ?? []}
        keyExtractor={(item) => String(item.id)}
        testID="staff-list"
        ListHeaderComponent={
          <>
            {isOwner && (
              <View style={styles.inviteSection}>
                <Text style={styles.sectionTitle}>Telefon ile Personel Davet Et</Text>
                <Text style={styles.hint}>
                  Davet edilecek kişinin Servisçep&apos;e kayıtlı olması gerekir.
                </Text>
                <View style={styles.phoneRow}>
                  <View style={styles.countryPicker} testID="staff-invite-country-code">
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
                    value={invitePhone}
                    onChangeText={setInvitePhone}
                    testID="staff-invite-phone"
                  />
                </View>
                {inviteError && (
                  <Text style={styles.error} testID="staff-invite-error">
                    {inviteError}
                  </Text>
                )}
                <Pressable
                  style={[styles.button, inviting && styles.buttonDisabled]}
                  onPress={handleInvite}
                  disabled={inviting}
                  testID="staff-invite-submit"
                >
                  {inviting ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>Davet Gönder</Text>
                  )}
                </Pressable>

                {invitations.map((invitation) => (
                  <View key={invitation.id} style={styles.invitationRow}>
                    <Text style={styles.invitationText}>
                      {invitation.phone} —{" "}
                      {INVITATION_STATUS_LABELS[invitation.status] ?? invitation.status}
                    </Text>
                    {invitation.status === "pending" && (
                      <Pressable onPress={() => handleRevokeInvitation(invitation)}>
                        <Text style={styles.revokeLink}>İptal Et</Text>
                      </Pressable>
                    )}
                  </View>
                ))}
              </View>
            )}

            {error && <Text style={styles.error}>{error}</Text>}
            {!error && staffMembers === null && (
              <View style={styles.center}>
                <ActivityIndicator />
              </View>
            )}
            {!error && staffMembers !== null && staffMembers.length === 0 && (
              <View style={styles.center}>
                <Text style={styles.emptyText}>Henüz personel yok.</Text>
              </View>
            )}
          </>
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={item.is_active ? styles.badgeActive : styles.badgeInactive}>
                {item.is_active ? "Aktif" : "Pasif"}
              </Text>
            </View>
            {isOwner && (
              <Pressable
                onPress={() => openPermissions(item)}
                style={styles.permissionsButton}
                testID={`staff-permissions-${item.id}`}
              >
                <Text style={styles.permissionsButtonText}>Yetkiler</Text>
              </Pressable>
            )}
          </View>
        )}
      />

      <Modal visible={permissionsFor !== null} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{permissionsFor?.name} — Yetkiler</Text>

            {membership === null && !permissionsError && <ActivityIndicator />}

            {membership === "not-linked" && (
              <Text style={styles.hint}>
                Bu personel davetle eklenmemiş (yerel kayıt) — düzenlenecek bir yetkisi yok.
              </Text>
            )}

            {membership !== null && membership !== "not-linked" && (
              <>
                <Pressable
                  style={[styles.button, savingPermissions && styles.buttonDisabled]}
                  onPress={handleGrantAll}
                  disabled={savingPermissions}
                  testID="staff-grant-all-permissions"
                >
                  <Text style={styles.buttonText}>Tüm Yetkileri Ver</Text>
                </Pressable>

                {PERMISSION_KEYS.map((key) => (
                  <View key={key} style={styles.permissionRow}>
                    <Text style={styles.permissionLabel}>{PERMISSION_LABELS[key]}</Text>
                    <Switch
                      value={membership[key]}
                      onValueChange={() => handleTogglePermission(key)}
                      disabled={savingPermissions}
                      testID={`staff-permission-${key}`}
                    />
                  </View>
                ))}

                <Pressable
                  style={[styles.dangerButton, savingPermissions && styles.buttonDisabled]}
                  onPress={handleEndMembership}
                  disabled={savingPermissions}
                  testID="staff-end-membership"
                >
                  <Text style={styles.dangerButtonText}>İşten Çıkar</Text>
                </Pressable>
              </>
            )}

            {permissionsError && <Text style={styles.error}>{permissionsError}</Text>}

            <Pressable onPress={closePermissions}>
              <Text style={styles.closeLink}>Kapat</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafafa" },
  center: { alignItems: "center", justifyContent: "center", padding: 24 },
  emptyText: { color: "#71717a" },
  error: { color: "#dc2626", padding: 8 },
  hint: { fontSize: 13, color: "#52525b" },
  sectionTitle: { fontSize: 15, fontWeight: "700", marginBottom: 4 },
  inviteSection: {
    padding: 16,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fff",
  },
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
  input: { borderWidth: 1, borderColor: "#d4d4d8", borderRadius: 8, padding: 10, fontSize: 15 },
  button: {
    backgroundColor: "#000",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontWeight: "600" },
  invitationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 6,
  },
  invitationText: { fontSize: 13, color: "#000" },
  revokeLink: { fontSize: 12, color: "#dc2626", textDecorationLine: "underline" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fff",
  },
  rowTitle: { fontSize: 15, fontWeight: "600", color: "#000" },
  badgeActive: { color: "#166534", fontSize: 13, fontWeight: "600" },
  badgeInactive: { color: "#71717a", fontSize: 13, fontWeight: "600" },
  permissionsButton: {
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  permissionsButtonText: { fontSize: 12, color: "#3f3f46" },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    padding: 24,
  },
  modalCard: { backgroundColor: "#fff", borderRadius: 12, padding: 20, gap: 12 },
  modalTitle: { fontSize: 17, fontWeight: "700" },
  permissionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  permissionLabel: { fontSize: 13, color: "#000", flex: 1, marginRight: 8 },
  dangerButton: {
    borderWidth: 1,
    borderColor: "#fecaca",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  dangerButtonText: { color: "#dc2626", fontWeight: "600" },
  closeLink: { textAlign: "center", color: "#71717a", textDecorationLine: "underline" },
});

import { Redirect, router, Stack } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { useAuth } from "@/lib/auth-context";

export default function AppLayout() {
  const { isLoading, isAuthenticated, tenantName, logout } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href="/login" />;
  }

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <Stack
      screenOptions={{
        headerTitle: tenantName ?? "ServisCep",
        headerRight: () => (
          <Pressable onPress={handleLogout} testID="logout-button" hitSlop={8}>
            <Text style={{ color: "#000", fontWeight: "600" }}>Çıkış</Text>
          </Pressable>
        ),
      }}
    >
      <Stack.Screen name="appointments/index" options={{ title: "Randevular" }} />
      <Stack.Screen name="appointments/[id]" options={{ title: "Randevu Detayı" }} />
      <Stack.Screen name="staff/index" options={{ title: "Personel" }} />
      <Stack.Screen name="services/index" options={{ title: "Hizmetler" }} />
    </Stack>
  );
}

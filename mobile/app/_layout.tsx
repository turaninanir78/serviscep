import { Stack } from "expo-router";

import { AuthProvider } from "@/lib/auth-context";

export default function RootLayout() {
  return (
    <AuthProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="login" options={{ headerShown: true, title: "Giriş Yap" }} />
        <Stack.Screen name="register" options={{ headerShown: true, title: "Kayıt Ol" }} />
        <Stack.Screen name="(app)" />
      </Stack>
    </AuthProvider>
  );
}

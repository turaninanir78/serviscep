import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

// Web'de httpOnly cookie kullanan panelin aksine, native app'lerin tarayici
// cookie jar'i yok - JWT burada dogrudan secure storage'a (iOS Keychain /
// Android Keystore) yaziliyor. expo-secure-store WEB'DE DESTEKLENMIYOR
// (bkz. https://docs.expo.dev/versions/latest/sdk/securestore/ - sadece
// Android/iOS/tvOS) - bu depoda gercek bir Android/iOS emulator/simulator
// erisimi olmadigi icin akisi `expo start --web` ile dogrulayabilmek adina
// web'de localStorage'a dusuluyor. GERCEK bir native build'de bu dal HIC
// calismaz, her zaman SecureStore kullanilir.
const TOKEN_KEY = "serviscep_access_token";

export async function getToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(TOKEN_KEY, token);
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.removeItem(TOKEN_KEY);
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

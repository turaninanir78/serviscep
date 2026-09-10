import { Alert, Platform } from "react-native";

// react-native-web'de Alert.alert'in gercek bir uygulamasi yok - cagirmak
// hicbir seye yol acmiyor (buton callback'leri hic tetiklenmiyor). Native'de
// (iOS/Android) Alert.alert standart ve guvenilir calisiyor; web'de bunun
// yerine tarayicinin kendi window.confirm()'una dusuyoruz.
export function confirmThen(message: string, action: () => void): void {
  if (Platform.OS === "web") {
    if (typeof window !== "undefined" && window.confirm(message)) {
      action();
    }
    return;
  }

  Alert.alert("Onay", message, [
    { text: "Vazgeç", style: "cancel" },
    { text: "Evet", style: "destructive", onPress: action },
  ]);
}

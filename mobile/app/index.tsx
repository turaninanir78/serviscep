import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/lib/auth-context";

// Web'deki "/" yonlendirme sayfasinin mobil karsiligi - token'in gercekten
// gecerli olup olmadigi (sadece var olup olmadigi degil) AuthProvider
// tarafindan /tenants/me ile dogrulaniyor.
export default function Index() {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return <Redirect href={isAuthenticated ? "/(app)/appointments" : "/login"} />;
}

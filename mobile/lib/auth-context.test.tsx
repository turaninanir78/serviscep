import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import { api } from "./api";
import { AuthProvider, useAuth } from "./auth-context";
import { clearToken, getToken, setToken } from "./storage";

jest.mock("./api");
jest.mock("./storage");

const mockedApi = api as jest.Mocked<typeof api>;
const mockedGetToken = getToken as jest.MockedFunction<typeof getToken>;
const mockedSetToken = setToken as jest.MockedFunction<typeof setToken>;
const mockedClearToken = clearToken as jest.MockedFunction<typeof clearToken>;

function Probe() {
  const { isLoading, isAuthenticated, tenantName, tenantTimezone, login, logout } = useAuth();
  return (
    <>
      <Text testID="state">
        {JSON.stringify({ isLoading, isAuthenticated, tenantName, tenantTimezone })}
      </Text>
      <Pressable testID="do-login" onPress={() => login("a@b.com", "pw")}>
        <Text>login</Text>
      </Pressable>
      <Pressable testID="do-logout" onPress={() => logout()}>
        <Text>logout</Text>
      </Pressable>
    </>
  );
}

function renderProbe() {
  const utils = render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  const readState = () => JSON.parse(utils.getByTestId("state").props.children);
  return { ...utils, readState };
}

describe("AuthProvider / useAuth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGetToken.mockResolvedValue(null);
  });

  test("depolanmis token yoksa mount sonrasi kimliksiz olarak isaretlenir", async () => {
    const { readState } = renderProbe();

    await waitFor(() => expect(readState().isLoading).toBe(false));
    expect(readState().isAuthenticated).toBe(false);
    expect(readState().tenantName).toBeNull();
    // Token olmadigi icin /tenants/me hic cagrilmamali.
    expect(mockedApi.getMyTenant).not.toHaveBeenCalled();
  });

  test("depolanmis GECERLI bir token varsa mount sonrasi otomatik kimlik dogrulanir", async () => {
    mockedGetToken.mockResolvedValue("stored-token");
    mockedApi.getMyTenant.mockResolvedValue({
      id: 1,
      name: "Var Olan Kuaför",
      timezone: "America/New_York",
      my_role: "owner",
      my_permissions: [],
    });

    const { readState } = renderProbe();

    await waitFor(() => expect(readState().isLoading).toBe(false));
    expect(readState().isAuthenticated).toBe(true);
    expect(readState().tenantName).toBe("Var Olan Kuaför");
    expect(readState().tenantTimezone).toBe("America/New_York");
  });

  test("kimliksizken tenantTimezone varsayilan (backend'in kolon varsayilaniyla ayni) degerdedir", async () => {
    const { readState } = renderProbe();
    await waitFor(() => expect(readState().isLoading).toBe(false));
    expect(readState().tenantTimezone).toBe("Europe/Istanbul");
  });

  test("depolanmis token GECERSIZSE (suresi dolmus/gecersiz) kimliksiz sayilir", async () => {
    mockedGetToken.mockResolvedValue("expired-token");
    mockedApi.getMyTenant.mockRejectedValue(new Error("401"));

    const { readState } = renderProbe();

    await waitFor(() => expect(readState().isLoading).toBe(false));
    expect(readState().isAuthenticated).toBe(false);
  });

  test("basarili login sonrasi token secure storage'a yazilir ve tenant bilgisi yuklenir", async () => {
    mockedApi.login.mockResolvedValue({ access_token: "fresh-token", token_type: "bearer" });
    mockedApi.getMyTenant.mockResolvedValue({
      id: 2,
      name: "Yeni Kuaför",
      timezone: "Europe/Istanbul",
      my_role: "owner",
      my_permissions: [],
    });

    const { readState, getByTestId } = renderProbe();
    await waitFor(() => expect(readState().isLoading).toBe(false));

    fireEvent.press(getByTestId("do-login"));

    await waitFor(() => expect(readState().isAuthenticated).toBe(true));
    expect(readState().tenantName).toBe("Yeni Kuaför");
    expect(mockedApi.login).toHaveBeenCalledWith("a@b.com", "pw");
    expect(mockedSetToken).toHaveBeenCalledWith("fresh-token");
  });

  test("logout secure storage'dan token'i siler ve kimliksiz duruma doner", async () => {
    mockedGetToken.mockResolvedValue("stored-token");
    mockedApi.getMyTenant.mockResolvedValue({
      id: 1,
      name: "Kuaför",
      timezone: "Europe/Istanbul",
      my_role: "owner",
      my_permissions: [],
    });

    const { readState, getByTestId } = renderProbe();
    await waitFor(() => expect(readState().isAuthenticated).toBe(true));

    fireEvent.press(getByTestId("do-logout"));

    await waitFor(() => expect(readState().isAuthenticated).toBe(false));
    expect(readState().tenantName).toBeNull();
    expect(mockedClearToken).toHaveBeenCalledTimes(1);
  });
});

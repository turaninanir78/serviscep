import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";

import { api } from "@/lib/api";
import RegisterScreen from "./register";

jest.mock("@/lib/api");
const mockCompleteRegistration = jest.fn<
  (
    registrationToken: string,
    tenantName: string,
    password: string,
    acceptedTerms: boolean,
  ) => Promise<void>
>();
jest.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ completeRegistration: mockCompleteRegistration }),
}));
// Ayni jest.mock hoisting sebebiyle (bkz. new.test.tsx'teki aciklama) router
// disaridan bir degiskene degil, factory'nin kendi icine tasiniyor.
jest.mock("expo-router", () => {
  const { Text } = require("react-native");
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    Link: ({ children, ...props }: any) => <Text {...props}>{children}</Text>,
  };
});

const mockedApi = api as jest.Mocked<typeof api>;
const mockRouter = router as jest.Mocked<typeof router>;

describe("RegisterScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("telefon -> kod -> şifre üç adımını sırayla tamamlayıp panele yönlendirir", async () => {
    mockedApi.requestRegisterOtp.mockResolvedValue({ message: "ok", debug_code: "123456" });
    mockedApi.verifyRegisterOtp.mockResolvedValue({ registration_token: "reg-token-abc" });
    mockCompleteRegistration.mockResolvedValue(undefined);

    const { getByTestId, findByText } = render(<RegisterScreen />);

    fireEvent.changeText(getByTestId("register-phone"), "5321234567");
    fireEvent.press(getByTestId("register-request-otp"));

    await waitFor(() =>
      expect(mockedApi.requestRegisterOtp).toHaveBeenCalledWith("+90", "5321234567"),
    );
    await findByText(/gönderilen kodu girin/);

    fireEvent.changeText(getByTestId("register-otp-code"), "999999");
    fireEvent.press(getByTestId("register-verify-otp"));

    await waitFor(() =>
      expect(mockedApi.verifyRegisterOtp).toHaveBeenCalledWith("+90", "5321234567", "999999"),
    );
    await waitFor(() => expect(getByTestId("register-tenant-name")).toBeTruthy());

    fireEvent.changeText(getByTestId("register-tenant-name"), "Test Kuaför");
    fireEvent.changeText(getByTestId("register-password"), "s3cret-pw");
    fireEvent.press(getByTestId("register-accept-terms"));
    fireEvent.press(getByTestId("register-submit"));

    await waitFor(() =>
      expect(mockCompleteRegistration).toHaveBeenCalledWith(
        "reg-token-abc",
        "Test Kuaför",
        "s3cret-pw",
        true,
      ),
    );
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/(app)/appointments"));
  });

  test("onay kutusu işaretlenmeden kayıt gönderilemez", async () => {
    mockedApi.requestRegisterOtp.mockResolvedValue({ message: "ok", debug_code: "123456" });
    mockedApi.verifyRegisterOtp.mockResolvedValue({ registration_token: "reg-token-abc" });

    const { getByTestId } = render(<RegisterScreen />);

    fireEvent.changeText(getByTestId("register-phone"), "5321234567");
    fireEvent.press(getByTestId("register-request-otp"));
    await waitFor(() => expect(getByTestId("register-otp-code")).toBeTruthy());

    fireEvent.changeText(getByTestId("register-otp-code"), "123456");
    fireEvent.press(getByTestId("register-verify-otp"));
    await waitFor(() => expect(getByTestId("register-tenant-name")).toBeTruthy());

    fireEvent.press(getByTestId("register-submit"));

    expect(mockCompleteRegistration).not.toHaveBeenCalled();
  });

  test("yanlış kod girilirse hata gösterilir, şifre adımına geçilmez", async () => {
    mockedApi.requestRegisterOtp.mockResolvedValue({ message: "ok", debug_code: null });
    mockedApi.verifyRegisterOtp.mockRejectedValue(new Error("Kod hatali."));

    const { getByTestId, queryByTestId } = render(<RegisterScreen />);

    fireEvent.changeText(getByTestId("register-phone"), "5321234567");
    fireEvent.press(getByTestId("register-request-otp"));
    await waitFor(() => expect(getByTestId("register-otp-code")).toBeTruthy());

    fireEvent.changeText(getByTestId("register-otp-code"), "000000");
    fireEvent.press(getByTestId("register-verify-otp"));

    await waitFor(() => expect(getByTestId("register-error")).toBeTruthy());
    expect(queryByTestId("register-tenant-name")).toBeNull();
  });
});

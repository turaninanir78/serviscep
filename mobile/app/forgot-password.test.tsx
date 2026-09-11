import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";

import { api } from "@/lib/api";
import ForgotPasswordScreen from "./forgot-password";

jest.mock("@/lib/api");
jest.mock("expo-router", () => {
  const { Text } = require("react-native");
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    Link: ({ children, ...props }: any) => <Text {...props}>{children}</Text>,
  };
});

const mockedApi = api as jest.Mocked<typeof api>;
const mockRouter = router as jest.Mocked<typeof router>;

describe("ForgotPasswordScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("email'i olmayan kullanıcı için otomatik SMS akışı: telefon -> kod -> yeni şifre", async () => {
    mockedApi.requestPasswordResetOtp.mockResolvedValue({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms"],
      debug_code: "123456",
    });
    mockedApi.verifyPasswordResetOtp.mockResolvedValue({ reset_token: "reset-token-abc" });
    mockedApi.completePasswordReset.mockResolvedValue(undefined);

    const { getByTestId, findByText } = render(<ForgotPasswordScreen />);

    fireEvent.changeText(getByTestId("forgot-password-phone"), "5321234567");
    fireEvent.press(getByTestId("forgot-password-request-otp"));

    await waitFor(() =>
      expect(mockedApi.requestPasswordResetOtp).toHaveBeenCalledWith("+90", "5321234567"),
    );
    await findByText(/gönderilen kodu girin/);

    fireEvent.changeText(getByTestId("forgot-password-otp-code"), "123456");
    fireEvent.press(getByTestId("forgot-password-verify-otp"));

    await waitFor(() =>
      expect(mockedApi.verifyPasswordResetOtp).toHaveBeenCalledWith(
        "+90",
        "5321234567",
        "123456",
      ),
    );
    await waitFor(() => expect(getByTestId("forgot-password-new-password")).toBeTruthy());

    fireEvent.changeText(getByTestId("forgot-password-new-password"), "Yeni-pw1!");
    fireEvent.press(getByTestId("forgot-password-submit"));

    await waitFor(() =>
      expect(mockedApi.completePasswordReset).toHaveBeenCalledWith(
        "reset-token-abc",
        "Yeni-pw1!",
      ),
    );
    await waitFor(() => expect(getByTestId("forgot-password-go-to-login")).toBeTruthy());

    fireEvent.press(getByTestId("forgot-password-go-to-login"));
    expect(mockRouter.replace).toHaveBeenCalledWith("/login");
  });

  test("email'i olan kullanıcı için kanal seçimi sunulur ve seçilen kanalla kod istenir", async () => {
    mockedApi.requestPasswordResetOtp.mockResolvedValueOnce({
      message: "ok",
      channel_choice_required: true,
      available_channels: ["sms", "email"],
      debug_code: null,
    });

    const { getByTestId, findByText } = render(<ForgotPasswordScreen />);

    fireEvent.changeText(getByTestId("forgot-password-phone"), "5321234567");
    fireEvent.press(getByTestId("forgot-password-request-otp"));

    await findByText(/nereye göndermek istersiniz/);
    expect(mockedApi.requestPasswordResetOtp).toHaveBeenCalledTimes(1);

    mockedApi.requestPasswordResetOtp.mockResolvedValueOnce({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms", "email"],
      debug_code: "777777",
    });

    fireEvent.press(getByTestId("forgot-password-channel-email"));

    await waitFor(() =>
      expect(mockedApi.requestPasswordResetOtp).toHaveBeenNthCalledWith(
        2,
        "+90",
        "5321234567",
        "email",
      ),
    );
    await findByText(/E-postanıza gönderilen kodu girin/);
  });

  test("yanlış kod girilirse hata gösterilir, şifre adımına geçilmez", async () => {
    mockedApi.requestPasswordResetOtp.mockResolvedValue({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms"],
      debug_code: null,
    });
    mockedApi.verifyPasswordResetOtp.mockRejectedValue(new Error("Kod hatali."));

    const { getByTestId, queryByTestId } = render(<ForgotPasswordScreen />);

    fireEvent.changeText(getByTestId("forgot-password-phone"), "5321234567");
    fireEvent.press(getByTestId("forgot-password-request-otp"));
    await waitFor(() => expect(getByTestId("forgot-password-otp-code")).toBeTruthy());

    fireEvent.changeText(getByTestId("forgot-password-otp-code"), "000000");
    fireEvent.press(getByTestId("forgot-password-verify-otp"));

    await waitFor(() => expect(getByTestId("forgot-password-error")).toBeTruthy());
    expect(queryByTestId("forgot-password-new-password")).toBeNull();
  });
});

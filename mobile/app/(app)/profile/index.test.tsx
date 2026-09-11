import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import ProfileScreen from "./index";

jest.mock("@/lib/api");
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
}));

const mockedApi = api as jest.Mocked<typeof api>;

const phoneOnlyUser: User = { id: 1, tenant_id: 10, email: null, phone: "+905321234567", role: "owner" };

describe("ProfileScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("email'i olmayan hesap icin kod isteyip dogrulayarak email eklenir, buton sonra 'Degistir'e doner", async () => {
    mockedApi.getMe.mockResolvedValue(phoneOnlyUser);
    mockedApi.requestAddEmailOtp.mockResolvedValue({ message: "ok", debug_code: "654321" });
    mockedApi.verifyAddEmail.mockResolvedValue({ ...phoneOnlyUser, email: "sahip@example.com" });

    const { getByTestId, findByTestId, getByText, queryByText } = render(<ProfileScreen />);

    await findByTestId("profile-phone");
    expect(getByText("+905321234567")).toBeTruthy();
    expect(getByText("Eklenmemiş")).toBeTruthy();
    expect(getByText("E-posta Ekle")).toBeTruthy();

    fireEvent.press(getByTestId("profile-add-email"));
    fireEvent.changeText(getByTestId("profile-email-input"), "sahip@example.com");
    fireEvent.press(getByTestId("profile-request-email-otp"));

    await waitFor(() =>
      expect(mockedApi.requestAddEmailOtp).toHaveBeenCalledWith("sahip@example.com"),
    );
    await findByTestId("profile-email-otp-code");

    fireEvent.changeText(getByTestId("profile-email-otp-code"), "654321");
    fireEvent.press(getByTestId("profile-verify-email-otp"));

    await waitFor(() =>
      expect(mockedApi.verifyAddEmail).toHaveBeenCalledWith("sahip@example.com", "654321"),
    );
    await waitFor(() => expect(getByText("sahip@example.com")).toBeTruthy());
    expect(queryByText("Eklenmemiş")).toBeNull();
    expect(getByText("E-postamı Değiştir")).toBeTruthy();
  });

  test("email'i zaten olan hesap icin buton 'E-postamı Değiştir' olarak gosterilir", async () => {
    mockedApi.getMe.mockResolvedValue({ ...phoneOnlyUser, email: "zaten@example.com" });

    const { findByTestId, getByText, queryByText } = render(<ProfileScreen />);

    await findByTestId("profile-email");
    expect(queryByText("E-posta Ekle")).toBeNull();
    expect(getByText("E-postamı Değiştir")).toBeTruthy();
  });

  test("'Telefon Numaramı Değiştir' akisi kod isteyip dogrulayarak telefonu gunceller", async () => {
    mockedApi.getMe.mockResolvedValue(phoneOnlyUser);
    mockedApi.requestChangePhoneOtp.mockResolvedValue({ message: "ok", debug_code: "222222" });
    mockedApi.verifyChangePhoneOtp.mockResolvedValue({
      ...phoneOnlyUser,
      phone: "+905339998877",
    });

    const { getByTestId, findByTestId, getByText } = render(<ProfileScreen />);

    await findByTestId("profile-phone");
    fireEvent.press(getByTestId("profile-change-phone"));
    fireEvent.changeText(getByTestId("profile-phone-input"), "5339998877");
    fireEvent.press(getByTestId("profile-request-phone-otp"));

    await waitFor(() =>
      expect(mockedApi.requestChangePhoneOtp).toHaveBeenCalledWith("+90", "5339998877"),
    );
    await findByTestId("profile-phone-otp-code");

    fireEvent.changeText(getByTestId("profile-phone-otp-code"), "222222");
    fireEvent.press(getByTestId("profile-verify-phone-otp"));

    await waitFor(() =>
      expect(mockedApi.verifyChangePhoneOtp).toHaveBeenCalledWith("+90", "5339998877", "222222"),
    );
    await waitFor(() => expect(getByText("+905339998877")).toBeTruthy());
  });

  test("'Şifremi Değiştir' akisi basarili olunca onay mesaji gosterir", async () => {
    mockedApi.getMe.mockResolvedValue(phoneOnlyUser);
    mockedApi.changePassword.mockResolvedValue(undefined);

    const { getByTestId, findByTestId } = render(<ProfileScreen />);

    await findByTestId("profile-phone");
    fireEvent.press(getByTestId("profile-change-password"));
    fireEvent.changeText(getByTestId("profile-current-password"), "Eskisi1!");
    fireEvent.changeText(getByTestId("profile-new-password"), "Yenisi1!");
    fireEvent.press(getByTestId("profile-submit-password"));

    await waitFor(() =>
      expect(mockedApi.changePassword).toHaveBeenCalledWith("Eskisi1!", "Yenisi1!"),
    );
    await findByTestId("profile-password-success");
  });

  test("yanlis mevcut sifre girilirse hata gosterilir", async () => {
    mockedApi.getMe.mockResolvedValue(phoneOnlyUser);
    mockedApi.changePassword.mockRejectedValue(new Error("401"));

    const { getByTestId, findByTestId } = render(<ProfileScreen />);

    await findByTestId("profile-phone");
    fireEvent.press(getByTestId("profile-change-password"));
    fireEvent.changeText(getByTestId("profile-current-password"), "Yanlis1!");
    fireEvent.changeText(getByTestId("profile-new-password"), "Yenisi1!");
    fireEvent.press(getByTestId("profile-submit-password"));

    await findByTestId("profile-password-error");
  });
});

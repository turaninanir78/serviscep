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

  test("email'i olmayan hesap icin kod isteyip dogrulayarak email eklenir", async () => {
    mockedApi.getMe.mockResolvedValue(phoneOnlyUser);
    mockedApi.requestAddEmailOtp.mockResolvedValue({ message: "ok", debug_code: "654321" });
    mockedApi.verifyAddEmail.mockResolvedValue({ ...phoneOnlyUser, email: "sahip@example.com" });

    const { getByTestId, findByTestId, getByText, queryByText } = render(<ProfileScreen />);

    await findByTestId("profile-phone");
    expect(getByText("+905321234567")).toBeTruthy();
    expect(getByText("Eklenmemiş")).toBeTruthy();

    fireEvent.press(getByTestId("profile-add-email"));
    fireEvent.changeText(getByTestId("profile-email-input"), "sahip@example.com");
    fireEvent.press(getByTestId("profile-request-otp"));

    await waitFor(() =>
      expect(mockedApi.requestAddEmailOtp).toHaveBeenCalledWith("sahip@example.com"),
    );
    await findByTestId("profile-otp-code");

    fireEvent.changeText(getByTestId("profile-otp-code"), "654321");
    fireEvent.press(getByTestId("profile-verify-otp"));

    await waitFor(() =>
      expect(mockedApi.verifyAddEmail).toHaveBeenCalledWith("sahip@example.com", "654321"),
    );
    await waitFor(() => expect(getByText("sahip@example.com")).toBeTruthy());
    expect(queryByText("Eklenmemiş")).toBeNull();
  });

  test("email'i zaten olan hesap icin 'E-posta Ekle' butonu gosterilmez", async () => {
    mockedApi.getMe.mockResolvedValue({ ...phoneOnlyUser, email: "zaten@example.com" });

    const { findByTestId, queryByTestId } = render(<ProfileScreen />);

    await findByTestId("profile-email");
    expect(queryByTestId("profile-add-email")).toBeNull();
  });
});

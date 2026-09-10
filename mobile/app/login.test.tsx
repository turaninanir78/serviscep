import { beforeEach, describe, expect, jest, test } from "@jest/globals";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";

import LoginScreen from "./login";

const mockLogin = jest.fn<(emailOrPhone: string, password: string) => Promise<void>>();
jest.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ login: mockLogin }),
}));
jest.mock("expo-router", () => {
  const { Text } = require("react-native");
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    Link: ({ children, ...props }: any) => <Text {...props}>{children}</Text>,
  };
});

const mockRouter = router as jest.Mocked<typeof router>;

describe("LoginScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("tek alana girilen değer (telefon ya da email) login'e email_or_phone olarak iletilir", async () => {
    mockLogin.mockResolvedValue(undefined);

    const { getByTestId } = render(<LoginScreen />);

    fireEvent.changeText(getByTestId("login-identifier"), "5321234567");
    fireEvent.changeText(getByTestId("login-password"), "s3cret-pw");
    fireEvent.press(getByTestId("login-submit"));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith("5321234567", "s3cret-pw"));
    await waitFor(() =>
      expect(mockRouter.replace).toHaveBeenCalledWith("/(app)/appointments"),
    );
  });

  test("hatalı giriş bilgilerinde hata gösterilir, yönlendirme yapılmaz", async () => {
    mockLogin.mockRejectedValue(new Error("401"));

    const { getByTestId } = render(<LoginScreen />);

    fireEvent.changeText(getByTestId("login-identifier"), "yanlis@example.com");
    fireEvent.changeText(getByTestId("login-password"), "wrong-pw");
    fireEvent.press(getByTestId("login-submit"));

    await waitFor(() => expect(getByTestId("login-error")).toBeTruthy());
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });
});

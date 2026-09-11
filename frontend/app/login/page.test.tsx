import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import LoginPage from "./page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("LoginPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    pushMock.mockClear();
  });

  test("tek 'E-posta veya Telefon' alanına girilen değer email_or_phone olarak login'e gönderilir", async () => {
    const user = userEvent.setup();
    const login = vi.spyOn(api, "login").mockResolvedValue(undefined);

    render(<LoginPage />);

    await user.type(screen.getByLabelText("E-posta veya Telefon"), "5321234567");
    await user.type(screen.getByLabelText("Şifre"), "s3cret-pw");
    await user.click(screen.getByRole("button", { name: "Giriş Yap" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("5321234567", "s3cret-pw"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/appointments"));
  });

  test("hatalı giriş bilgilerinde hata mesajı gösterilir, yönlendirme yapılmaz", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "login").mockRejectedValue(new ApiError(401, "Invalid email or password"));

    render(<LoginPage />);

    await user.type(screen.getByLabelText("E-posta veya Telefon"), "yanlis@example.com");
    await user.type(screen.getByLabelText("Şifre"), "wrong-pw");
    await user.click(screen.getByRole("button", { name: "Giriş Yap" }));

    expect(await screen.findByText(/Giriş bilgileriniz geçersiz/)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});

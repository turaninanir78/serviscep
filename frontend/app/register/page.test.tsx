import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import RegisterPage from "./page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("RegisterPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    pushMock.mockClear();
  });

  test("telefon -> kod -> şifre üç adımını sırayla tamamlayıp panele yönlendirir", async () => {
    const user = userEvent.setup();
    const requestOtp = vi.spyOn(api, "requestRegisterOtp").mockResolvedValue({
      message: "ok",
      debug_code: "123456",
    });
    const verifyOtp = vi
      .spyOn(api, "verifyRegisterOtp")
      .mockResolvedValue({ registration_token: "reg-token-abc" });
    const complete = vi.spyOn(api, "completeRegister").mockResolvedValue(undefined);

    render(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("+90", "5321234567"));
    expect(await screen.findByText(/gönderilen kodu girin/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "999999");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(verifyOtp).toHaveBeenCalledWith("+90", "5321234567", "999999"),
    );
    expect(await screen.findByLabelText("Firma Adı")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Firma Adı"), "Test Kuaför");
    await user.type(screen.getByLabelText("Şifre"), "s3cret-pw");
    await user.click(screen.getByRole("button", { name: "Kayıt Ol" }));

    await waitFor(() =>
      expect(complete).toHaveBeenCalledWith("reg-token-abc", "Test Kuaför", "s3cret-pw"),
    );
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/appointments"));
  });

  test("yanlış kod girilirse hata gösterilir ve şifre adımına geçilmez", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "requestRegisterOtp").mockResolvedValue({ message: "ok", debug_code: null });
    vi.spyOn(api, "verifyRegisterOtp").mockRejectedValue(new ApiError(400, "Kod hatali."));

    render(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "000000");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    expect(await screen.findByText(/İstek geçersiz/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Firma Adı")).not.toBeInTheDocument();
  });

  test("kodu tekrar gönder, aynı telefon numarasıyla OTP isteğini tekrar tetikler", async () => {
    const user = userEvent.setup();
    const requestOtp = vi
      .spyOn(api, "requestRegisterOtp")
      .mockResolvedValue({ message: "ok", debug_code: null });
    vi.spyOn(api, "verifyRegisterOtp");

    render(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.click(screen.getByRole("button", { name: "Kodu tekrar gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledTimes(2));
    expect(requestOtp).toHaveBeenNthCalledWith(2, "+90", "5321234567");
  });
});

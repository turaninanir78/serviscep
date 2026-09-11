import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import ForgotPasswordPage from "./page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("ForgotPasswordPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    pushMock.mockClear();
  });

  test("email'i olmayan kullanıcı için otomatik SMS akışı: telefon -> kod -> yeni şifre", async () => {
    const user = userEvent.setup();
    const requestOtp = vi.spyOn(api, "requestPasswordResetOtp").mockResolvedValue({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms"],
      debug_code: "123456",
    });
    const verifyOtp = vi
      .spyOn(api, "verifyPasswordResetOtp")
      .mockResolvedValue({ reset_token: "reset-token-abc" });
    const complete = vi.spyOn(api, "completePasswordReset").mockResolvedValue(undefined);

    render(<ForgotPasswordPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Devam Et" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("+90", "5321234567"));
    expect(await screen.findByText(/gönderilen kodu girin/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "123456");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(verifyOtp).toHaveBeenCalledWith("+90", "5321234567", "123456"),
    );
    expect(await screen.findByLabelText("Yeni Şifre")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Yeni Şifre"), "Yeni-pw1!");
    await user.click(screen.getByRole("button", { name: "Şifreyi Güncelle" }));

    await waitFor(() =>
      expect(complete).toHaveBeenCalledWith("reset-token-abc", "Yeni-pw1!"),
    );
    expect(await screen.findByText(/Şifreniz güncellendi/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Giriş Yap" }));
    expect(pushMock).toHaveBeenCalledWith("/login");
  });

  test("email'i olan kullanıcı için kanal seçimi sunulur ve seçilen kanalla kod istenir", async () => {
    const user = userEvent.setup();
    const requestOtp = vi.spyOn(api, "requestPasswordResetOtp").mockResolvedValueOnce({
      message: "ok",
      channel_choice_required: true,
      available_channels: ["sms", "email"],
      debug_code: null,
    });

    render(<ForgotPasswordPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Devam Et" }));

    expect(await screen.findByText(/nereye göndermek istersiniz/)).toBeInTheDocument();
    // Kanal henuz secilmedigi icin kod istekte GONDERILMEMIS olmali.
    expect(requestOtp).toHaveBeenCalledTimes(1);

    requestOtp.mockResolvedValueOnce({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms", "email"],
      debug_code: "777777",
    });

    await user.click(screen.getByRole("button", { name: "E-posta ile Gönder" }));

    await waitFor(() =>
      expect(requestOtp).toHaveBeenNthCalledWith(2, "+90", "5321234567", "email"),
    );
    expect(await screen.findByText(/E-postanıza gönderilen kodu girin/)).toBeInTheDocument();
  });

  test("kodu tekrar gönder, aynı telefon ve kanalla OTP isteğini tekrar tetikler", async () => {
    const user = userEvent.setup();
    const requestOtp = vi.spyOn(api, "requestPasswordResetOtp").mockResolvedValue({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms"],
      debug_code: null,
    });
    vi.spyOn(api, "verifyPasswordResetOtp");

    render(<ForgotPasswordPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Devam Et" }));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.click(screen.getByRole("button", { name: "Kodu tekrar gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledTimes(2));
    expect(requestOtp).toHaveBeenNthCalledWith(2, "+90", "5321234567", undefined);
  });

  test("yanlış kod girilirse hata gösterilir ve şifre adımına geçilmez", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "requestPasswordResetOtp").mockResolvedValue({
      message: "ok",
      channel_choice_required: false,
      available_channels: ["sms"],
      debug_code: null,
    });
    vi.spyOn(api, "verifyPasswordResetOtp").mockRejectedValue(new ApiError(400, "Kod hatali."));

    render(<ForgotPasswordPage />);

    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5321234567");
    await user.click(screen.getByRole("button", { name: "Devam Et" }));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "000000");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    expect(await screen.findByText(/İstek geçersiz/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Yeni Şifre")).not.toBeInTheDocument();
  });
});

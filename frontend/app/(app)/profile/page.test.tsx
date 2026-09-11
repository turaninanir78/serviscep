import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import ProfilePage from "./page";

const phoneOnlyUser: User = { id: 1, tenant_id: 10, email: null, phone: "+905321234567", role: "owner" };

describe("ProfilePage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("email'i olmayan hesap için 'E-posta Ekle' akışı kod isteyip doğrulayarak email'i hesaba ekler", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMe").mockResolvedValue(phoneOnlyUser);
    const requestOtp = vi
      .spyOn(api, "requestAddEmailOtp")
      .mockResolvedValue({ message: "ok", debug_code: "654321" });
    const verifyEmail = vi.spyOn(api, "verifyAddEmail").mockResolvedValue({
      ...phoneOnlyUser,
      email: "sahip@example.com",
    });

    render(<ProfilePage />);

    expect(await screen.findByText("+905321234567")).toBeInTheDocument();
    expect(screen.getByText("Eklenmemiş")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "E-posta Ekle" }));
    await user.type(screen.getByLabelText("Yeni E-posta Adresi"), "sahip@example.com");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("sahip@example.com"));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "654321");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(verifyEmail).toHaveBeenCalledWith("sahip@example.com", "654321"),
    );
    expect(await screen.findByText("sahip@example.com")).toBeInTheDocument();
    // Artik email dolu oldugu icin buton "Degistir"e donusur.
    expect(screen.queryByRole("button", { name: "E-posta Ekle" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "E-postamı Değiştir" })).toBeInTheDocument();
  });

  test("email'i zaten olan hesap için buton 'E-postamı Değiştir' olarak gösterilir ve yeni bir email'e geçiş yapılabilir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMe").mockResolvedValue({ ...phoneOnlyUser, email: "eski@example.com" });
    const requestOtp = vi
      .spyOn(api, "requestAddEmailOtp")
      .mockResolvedValue({ message: "ok", debug_code: "111111" });
    vi.spyOn(api, "verifyAddEmail").mockResolvedValue({
      ...phoneOnlyUser,
      email: "yeni@example.com",
    });

    render(<ProfilePage />);

    expect(await screen.findByText("eski@example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "E-posta Ekle" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "E-postamı Değiştir" }));
    await user.type(screen.getByLabelText("Yeni E-posta Adresi"), "yeni@example.com");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("yeni@example.com"));
    await user.type(await screen.findByLabelText("Doğrulama Kodu"), "111111");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    expect(await screen.findByText("yeni@example.com")).toBeInTheDocument();
  });

  test("'Telefon Numaramı Değiştir' akışı kod isteyip doğrulayarak telefonu günceller", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMe").mockResolvedValue(phoneOnlyUser);
    const requestOtp = vi
      .spyOn(api, "requestChangePhoneOtp")
      .mockResolvedValue({ message: "ok", debug_code: "222222" });
    const verifyOtp = vi.spyOn(api, "verifyChangePhoneOtp").mockResolvedValue({
      ...phoneOnlyUser,
      phone: "+905339998877",
    });

    render(<ProfilePage />);

    await screen.findByText("+905321234567");
    await user.click(screen.getByRole("button", { name: "Telefon Numaramı Değiştir" }));
    await user.type(screen.getByPlaceholderText("5XX XXX XX XX"), "5339998877");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("+90", "5339998877"));
    await user.type(await screen.findByLabelText("Doğrulama Kodu"), "222222");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(verifyOtp).toHaveBeenCalledWith("+90", "5339998877", "222222"),
    );
    expect(await screen.findByText("+905339998877")).toBeInTheDocument();
  });

  test("'Şifremi Değiştir' akışı başarılı olunca onay mesajı gösterir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMe").mockResolvedValue(phoneOnlyUser);
    const changePassword = vi.spyOn(api, "changePassword").mockResolvedValue(undefined);

    render(<ProfilePage />);

    await screen.findByText("+905321234567");
    await user.click(screen.getByRole("button", { name: "Şifremi Değiştir" }));
    await user.type(screen.getByLabelText("Mevcut Şifre"), "Eskisi1!");
    await user.type(screen.getByLabelText("Yeni Şifre"), "Yenisi1!");
    await user.click(screen.getByRole("button", { name: "Şifreyi Güncelle" }));

    await waitFor(() => expect(changePassword).toHaveBeenCalledWith("Eskisi1!", "Yenisi1!"));
    expect(await screen.findByText("Şifreniz güncellendi.")).toBeInTheDocument();
  });

  test("yanlış mevcut şifre girilirse hata gösterilir", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "getMe").mockResolvedValue(phoneOnlyUser);
    vi.spyOn(api, "changePassword").mockRejectedValue(new ApiError(401, "Mevcut sifre yanlis."));

    render(<ProfilePage />);

    await screen.findByText("+905321234567");
    await user.click(screen.getByRole("button", { name: "Şifremi Değiştir" }));
    await user.type(screen.getByLabelText("Mevcut Şifre"), "Yanlis1!");
    await user.type(screen.getByLabelText("Yeni Şifre"), "Yenisi1!");
    await user.click(screen.getByRole("button", { name: "Şifreyi Güncelle" }));

    expect(await screen.findByText(/Giriş bilgileriniz geçersiz/)).toBeInTheDocument();
  });
});

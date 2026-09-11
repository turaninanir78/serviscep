import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { api } from "@/lib/api";
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
    await user.type(screen.getByLabelText("E-posta Adresi"), "sahip@example.com");
    await user.click(screen.getByRole("button", { name: "Kod Gönder" }));

    await waitFor(() => expect(requestOtp).toHaveBeenCalledWith("sahip@example.com"));
    await screen.findByLabelText("Doğrulama Kodu");

    await user.type(screen.getByLabelText("Doğrulama Kodu"), "654321");
    await user.click(screen.getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(verifyEmail).toHaveBeenCalledWith("sahip@example.com", "654321"),
    );
    expect(await screen.findByText("sahip@example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "E-posta Ekle" })).not.toBeInTheDocument();
  });

  test("email'i zaten olan hesap için 'E-posta Ekle' butonu gösterilmez", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({
      ...phoneOnlyUser,
      email: "zaten@example.com",
    });

    render(<ProfilePage />);

    expect(await screen.findByText("zaten@example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "E-posta Ekle" })).not.toBeInTheDocument();
  });
});

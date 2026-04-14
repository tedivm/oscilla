import { apiFetch } from "./client.js";
import type { TokenPairRead, UserRead } from "./types.js";

export async function login(
  email: string,
  password: string,
): Promise<TokenPairRead> {
  return apiFetch<TokenPairRead>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  email: string,
  password: string,
): Promise<UserRead> {
  return apiFetch<UserRead>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(refreshToken: string): Promise<void> {
  return apiFetch<void>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function me(): Promise<UserRead> {
  return apiFetch<UserRead>("/api/auth/me");
}

export async function refresh(refreshToken: string): Promise<TokenPairRead> {
  return apiFetch<TokenPairRead>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  return apiFetch<void>("/api/auth/request-password-reset", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<void> {
  return apiFetch<void>(`/auth/password-reset/${encodeURIComponent(token)}`, {
    method: "POST",
    body: JSON.stringify({ new_password: password }),
  });
}

export async function verifyEmail(token: string): Promise<void> {
  return apiFetch<void>(`/auth/verify/${encodeURIComponent(token)}`);
}

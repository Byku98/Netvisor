/** Auth API client — login, register, Google OAuth, logout, me. */

import { logger } from "@/utils/logger";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  hasGoogle: boolean;
  createdAt: string;
}

export interface AuthResponse {
  user: UserResponse;
}

/** Register a new local account. */
export async function register(
  username: string,
  email: string,
  password: string,
): Promise<AuthResponse> {
  const url = `${API_BASE}/auth/register`;
  logger.info("auth-api", `POST ${url}`, { username, email });

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = (error as { detail?: string }).detail ?? "Registration failed";
    logger.error("auth-api", `Register failed: ${response.status}`, { detail });
    throw new Error(detail);
  }

  const data = (await response.json()) as AuthResponse;
  logger.info("auth-api", "Register success", { userId: data.user.id });
  return data;
}

/** Login with username or email + password. */
export async function login(usernameOrEmail: string, password: string): Promise<AuthResponse> {
  const url = `${API_BASE}/auth/login`;
  logger.info("auth-api", `POST ${url}`, { usernameOrEmail });

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usernameOrEmail, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = (error as { detail?: string }).detail ?? "Login failed";
    logger.error("auth-api", `Login failed: ${response.status}`, { detail });
    throw new Error(detail);
  }

  const data = (await response.json()) as AuthResponse;
  logger.info("auth-api", "Login success", { userId: data.user.id });
  return data;
}

/** Login/register via Google ID token. */
export async function googleLogin(idToken: string): Promise<AuthResponse> {
  const url = `${API_BASE}/auth/google`;
  logger.info("auth-api", `POST ${url}`);

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = (error as { detail?: string }).detail ?? "Google login failed";
    logger.error("auth-api", `Google login failed: ${response.status}`, { detail });
    throw new Error(detail);
  }

  const data = (await response.json()) as AuthResponse;
  logger.info("auth-api", "Google login success", { userId: data.user.id });
  return data;
}

/** Logout — clears cookies. */
export async function logout(): Promise<void> {
  logger.info("auth-api", "Logout");
  await fetch(`${API_BASE}/auth/logout`, { method: "POST" });
}

/** Get current user from cookie. Returns null if not logged in. */
export async function fetchMe(): Promise<UserResponse | null> {
  logger.debug("auth-api", "GET /auth/me");
  const response = await fetch(`${API_BASE}/auth/me`);
  if (!response.ok) {
    logger.debug("auth-api", "Not authenticated", { status: response.status });
    return null;
  }
  const data = (await response.json()) as AuthResponse;
  logger.debug("auth-api", "Authenticated", { userId: data.user.id });
  return data.user;
}

/** Fetch sessions belonging to the current user. */
export async function fetchMySessions() {
  logger.debug("auth-api", "GET /users/me/sessions");
  const response = await fetch(`${API_BASE}/users/me/sessions`, {
    credentials: "include",
  });
  if (!response.ok) {
    logger.error("auth-api", "Failed to fetch sessions", { status: response.status });
    throw new Error("Failed to fetch sessions");
  }
  return response.json();
}

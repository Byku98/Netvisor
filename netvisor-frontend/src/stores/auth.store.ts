import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { UserResponse } from "@/api/auth.api";
import * as authApi from "@/api/auth.api";
import { logger } from "@/utils/logger";

interface AuthState {
  /** Current user, or null if not logged in. */
  user: UserResponse | null;
  /** Whether we're still checking auth state on mount. */
  isLoading: boolean;
  /** Last error message from an auth operation. */
  error: string | null;

  /** Check if user is logged in (call on app mount). */
  fetchMe: () => Promise<void>;
  /** Register a new local account. */
  register: (username: string, email: string, password: string) => Promise<void>;
  /** Login with username or email + password. */
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  /** Login via Google ID token. */
  googleLogin: (idToken: string) => Promise<void>;
  /** Logout and clear user. */
  logout: () => Promise<void>;
  /** Clear error state. */
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  devtools((set) => ({
    user: null,
    isLoading: true,
    error: null,

    fetchMe: async () => {
      logger.debug("auth-store", "fetchMe called");
      set({ isLoading: true });
      try {
        const user = await authApi.fetchMe();
        logger.info("auth-store", "fetchMe result", { user: user?.username ?? null });
        set({ user, isLoading: false });
      } catch (e) {
        logger.error("auth-store", "fetchMe failed", e);
        set({ user: null, isLoading: false });
      }
    },

    register: async (username, email, password) => {
      logger.info("auth-store", "register called", { username, email });
      set({ error: null });
      try {
        const { user } = await authApi.register(username, email, password);
        logger.info("auth-store", "register success", { userId: user.id });
        set({ user, error: null });
      } catch (e) {
        const msg = (e as Error).message;
        logger.error("auth-store", "register failed", { error: msg });
        set({ error: msg });
        throw e;
      }
    },

    login: async (usernameOrEmail, password) => {
      logger.info("auth-store", "login called", { usernameOrEmail });
      set({ error: null });
      try {
        const { user } = await authApi.login(usernameOrEmail, password);
        logger.info("auth-store", "login success", { userId: user.id });
        set({ user, error: null });
      } catch (e) {
        const msg = (e as Error).message;
        logger.error("auth-store", "login failed", { error: msg });
        set({ error: msg });
        throw e;
      }
    },

    googleLogin: async (idToken) => {
      logger.info("auth-store", "googleLogin called");
      set({ error: null });
      try {
        const { user } = await authApi.googleLogin(idToken);
        logger.info("auth-store", "googleLogin success", { userId: user.id });
        set({ user, error: null });
      } catch (e) {
        const msg = (e as Error).message;
        logger.error("auth-store", "googleLogin failed", { error: msg });
        set({ error: msg });
        throw e;
      }
    },

    logout: async () => {
      logger.info("auth-store", "logout called");
      await authApi.logout();
      set({ user: null, error: null });
    },

    clearError: () => set({ error: null }),
  }))
);

import { useState } from "react";
import { useAuthStore } from "@/stores/auth.store";
import { useUiStore } from "@/stores/ui.store";
import { useI18n, type Lang } from "@/i18n";
import { Network, LogIn, LogOut, ChevronDown, FolderOpen, Upload, Sun, Moon, Terminal } from "lucide-react";
import { LoginModal } from "./LoginModal";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  /** Navigate to home/upload screen. */
  onHome?: () => void;
  /** Show "My Sessions" link. */
  onMySessions?: () => void;
  /** Show "New Session" link (go back to upload). */
  onNewSession?: () => void;
  /** Extra content on the right side (e.g. GraphControls). */
  children?: React.ReactNode;
}

export function AppHeader({ onHome, onMySessions, onNewSession, children }: AppHeaderProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const debugEnabled = useUiStore((s) => s.debugEnabled);
  const toggleDebug = useUiStore((s) => s.toggleDebug);
  const { t, lang, setLang } = useI18n();
  const [showMenu, setShowMenu] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  return (
    <>
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <button
            onClick={onHome}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            title="Go to home"
          >
            <Network className="h-6 w-6 text-blue-500" />
            <h1 className="text-xl font-bold tracking-tight">NetVisor</h1>
          </button>

          <div className="flex items-center gap-3">
            {children}

            {/* Language switch EN | PL */}
            <div className="flex rounded-lg bg-zinc-800 p-0.5" title="Language / Język">
              {(["en", "pl"] as Lang[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  className={cn(
                    "px-2 py-1 rounded-md text-[11px] font-medium uppercase transition-colors",
                    lang === l ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200",
                  )}
                >
                  {l}
                </button>
              ))}
            </div>

            {/* Debug log toggle */}
            <label
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-zinc-800 cursor-pointer select-none hover:bg-zinc-700 transition-colors"
              title="Show/hide the debug log panel"
            >
              <input
                type="checkbox"
                checked={debugEnabled}
                onChange={toggleDebug}
                className="w-3 h-3 accent-blue-600 cursor-pointer"
              />
              <Terminal className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-[11px] text-zinc-400">{t("debug")}</span>
            </label>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </button>

            {user ? (
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors"
                >
                  <div className="h-6 w-6 rounded-full bg-blue-600 flex items-center justify-center text-xs font-medium">
                    {user.username[0].toUpperCase()}
                  </div>
                  <span className="text-sm text-zinc-300 max-w-[120px] truncate">
                    {user.username}
                  </span>
                  <ChevronDown className="h-3 w-3 text-zinc-500" />
                </button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 mt-1 w-48 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-50 py-1">
                      <div className="px-3 py-2 border-b border-zinc-800">
                        <p className="text-sm font-medium text-zinc-200 truncate">
                          {user.username}
                        </p>
                        <p className="text-xs text-zinc-500 truncate">{user.email}</p>
                      </div>
                      {onNewSession && (
                        <button
                          onClick={() => {
                            setShowMenu(false);
                            onNewSession();
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                        >
                          <Upload className="h-4 w-4" />
                          {t("newSession")}
                        </button>
                      )}
                      {onMySessions && (
                        <button
                          onClick={() => {
                            setShowMenu(false);
                            onMySessions();
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                        >
                          <FolderOpen className="h-4 w-4" />
                          {t("mySessions")}
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          logout();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                      >
                        <LogOut className="h-4 w-4" />
                        Logout
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <button
                onClick={() => setShowLoginModal(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors text-sm text-zinc-300"
              >
                <LogIn className="h-4 w-4" />
                {t("signIn")}
              </button>
            )}
          </div>
        </div>
      </header>

      <LoginModal open={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </>
  );
}
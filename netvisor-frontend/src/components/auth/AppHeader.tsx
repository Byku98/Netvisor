import { useState } from "react";
import { useAuthStore } from "@/stores/auth.store";
import { Network, LogIn, LogOut, ChevronDown, FolderOpen } from "lucide-react";
import { LoginModal } from "./LoginModal";

interface AppHeaderProps {
  /** Show back button and optional back handler. */
  onBack?: () => void;
  /** Show "My Sessions" link. */
  onMySessions?: () => void;
  /** Extra content on the right side (e.g. GraphControls). */
  children?: React.ReactNode;
}

export function AppHeader({ onBack, onMySessions, children }: AppHeaderProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [showMenu, setShowMenu] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  return (
    <>
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            {onBack && (
              <button
                onClick={onBack}
                className="text-zinc-500 hover:text-zinc-300 transition-colors mr-2"
                title="Back"
              >
                ←
              </button>
            )}
            <Network className="h-6 w-6 text-blue-500" />
            <h1 className="text-xl font-bold tracking-tight">NetVisor</h1>
          </div>

          <div className="flex items-center gap-3">
            {children}

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
                      {onMySessions && (
                        <button
                          onClick={() => {
                            setShowMenu(false);
                            onMySessions();
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                        >
                          <FolderOpen className="h-4 w-4" />
                          My Sessions
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
                Sign In
              </button>
            )}
          </div>
        </div>
      </header>

      <LoginModal open={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </>
  );
}
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as api from "../api";

const TOKEN_KEY = "phonics-arcade.token";

type SessionState =
  | { status: "loading" }
  | { status: "out" }
  | { status: "offline" } // a saved login exists, but the server could not be reached to check it
  | { status: "in"; player: api.Player; guest: boolean };

interface SessionActions {
  /** Checks the saved login again (after "offline"). */
  retry(): void;
  logIn(name: string, password: string): Promise<void>;
  register(name: string, password: string, interests: string[]): Promise<void>;
  playAsGuest(): Promise<void>;
  leave(): Promise<void>;
}

const SessionContext = createContext<(SessionState & SessionActions) | null>(null);

function toPlayer({ player_id, name, interests }: api.LoginResult): api.Player {
  return { player_id, name, interests };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: "loading" });

  const clear = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    api.setToken(null);
    setState({ status: "out" });
  }, []);

  // Page reload: check that the saved token still works and get the profile back.
  // Only a 401 means the login is gone; if the server is just unreachable, keep the login and offer a retry.
  const restore = useCallback(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (!saved) {
      setState({ status: "out" });
      return;
    }
    setState({ status: "loading" });
    api.setToken(saved);
    api.me().then(
      (player) => setState({ status: "in", player, guest: false }),
      (e) => (e instanceof api.ApiError && e.status === 401 ? clear() : setState({ status: "offline" })),
    );
  }, [clear]);

  useEffect(() => {
    api.setOnUnauthorized(clear);
    restore();
    return () => api.setOnUnauthorized(null);
  }, [clear, restore]);

  const actions = useMemo<SessionActions>(() => {
    const start = (result: api.LoginResult, guest: boolean) => {
      api.setToken(result.token);
      // A guest's token lives in memory only, so leaving or reloading the page ends the visit.
      if (!guest) localStorage.setItem(TOKEN_KEY, result.token);
      setState({ status: "in", player: toPlayer(result), guest });
    };
    return {
      retry: restore,
      logIn: async (name, password) => start(await api.login(name, password), false),
      register: async (name, password, interests) => start(await api.register(name, password, interests), false),
      playAsGuest: async () => start(await api.startGuest(), true),
      // For a guest, /logout also deletes their data on the server.
      leave: async () => {
        try {
          await api.logout();
        } catch {
          // already logged out, or the server is unreachable: leave anyway
        }
        clear();
      },
    };
  }, [clear, restore]);

  const value = useMemo(() => ({ ...state, ...actions }), [state, actions]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession needs a SessionProvider");
  return session;
}

/** The logged-in player. Only call inside the game shell, which is rendered after login. */
export function usePlayer(): api.Player {
  const session = useSession();
  if (session.status !== "in") throw new Error("usePlayer needs a logged-in player");
  return session.player;
}

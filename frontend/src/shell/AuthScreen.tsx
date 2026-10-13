import { useState, type FormEvent } from "react";
import { ApiError } from "../api";
import { useSession } from "./session";

type Mode = "login" | "register";

function messageFor(error: unknown, mode: Mode): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Wrong nickname or password.";
    if (error.status === 409) return "That nickname is taken. Try another one.";
    if (error.status === 422 && mode === "register") return "Check the nickname and password, then try again.";
    return error.message;
  }
  return "Something went wrong. Try again.";
}

export default function AuthScreen() {
  const session = useSession();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [interests, setInterests] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(messageFor(e, mode));
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "login") {
      void run(() => session.logIn(name, password));
    } else {
      const list = interests.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 5);
      void run(() => session.register(name, password, list));
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
  }

  return (
    <main className="auth">
      <h1>Phonics Arcade</h1>
      <p className="lead">Reading practice games you play with your voice.</p>

      <div className="card">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={mode === "login"} onClick={() => switchMode("login")}>
            Log in
          </button>
          <button role="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>
            Create account
          </button>
        </div>

        <form onSubmit={submit}>
          <label>
            Nickname
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={30}
              required
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              maxLength={128}
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" && <span className="hint">At least 8 characters.</span>}
          </label>
          {mode === "register" && (
            <label>
              Things you like (optional)
              <input
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="football, cooking, space"
              />
              <span className="hint">Up to 5, with commas between. Your stories will use them.</span>
            </label>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" type="submit" disabled={busy}>
            {mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>

      <div className="card guest">
        <button className="secondary" onClick={() => void run(session.playAsGuest)} disabled={busy}>
          Play as guest
        </button>
        <p className="hint">Guest progress isn't saved. Create an account to keep it.</p>
      </div>
    </main>
  );
}

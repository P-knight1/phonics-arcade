import { useState, type FormEvent } from "react";
import { ApiError } from "../api";
import { useSession } from "./session";

type Mode = "login" | "register";

function messageFor(error: unknown, mode: Mode): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "اسم المستخدم أو كلمة المرور غير صحيحة.";
    if (error.status === 409) return "هذا الاسم مستخدم. جرّب اسمًا آخر.";
    if (error.status === 422 && mode === "register") return "راجع الاسم وكلمة المرور ثم حاول مرة أخرى.";
    return error.message;
  }
  return "حدث خطأ. حاول مرة أخرى.";
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
      const list = interests.split(/[,،]/).map((s) => s.trim()).filter(Boolean).slice(0, 5);
      if (list.some((s) => s.length > 40)) {
        setError("كل اهتمام يصل إلى 40 حرفًا.");
        return;
      }
      void run(() => session.register(name, password, list));
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
  }

  return (
    <main className="auth">
      <h1 className="brand">
        <span className="brand-mark" aria-hidden="true">
          ح
        </span>
        صوت الحروف
      </h1>
      <p className="lead">ألعاب للتدرّب على القراءة بصوتك.</p>

      <div className="card">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={mode === "login"} onClick={() => switchMode("login")}>
            تسجيل الدخول
          </button>
          <button role="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>
            حساب جديد
          </button>
        </div>

        <form onSubmit={submit}>
          <label>
            اسم المستخدم
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={30}
              required
              autoComplete="username"
            />
          </label>
          <label>
            كلمة المرور
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              maxLength={128}
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" && <span className="hint">8 أحرف على الأقل.</span>}
          </label>
          {mode === "register" && (
            <label>
              ما تحبه (اختياري)
              <input
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="كرة القدم، الطبخ، الفضاء"
              />
              <span className="hint">حتى 5، بينها فواصل. ستُستخدم في قصصك.</span>
            </label>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" type="submit" disabled={busy}>
            {mode === "login" ? "دخول" : "إنشاء الحساب"}
          </button>
        </form>
      </div>

      <div className="card guest">
        <button className="secondary" onClick={() => void run(session.playAsGuest)} disabled={busy}>
          العب ضيفًا
        </button>
        <p className="hint">تقدّم الضيف لا يُحفظ. أنشئ حسابًا لتحتفظ به.</p>
      </div>
    </main>
  );
}

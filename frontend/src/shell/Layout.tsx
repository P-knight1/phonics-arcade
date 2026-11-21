import { Link, Outlet } from "react-router-dom";
import { DEBUG } from "./debug";
import { displayName, useSession } from "./session";

export default function Layout() {
  const session = useSession();
  if (session.status !== "in") return null;

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ح
          </span>
          صوت الحروف
        </Link>
        {DEBUG && <span className="badge">وضع التجربة</span>}
        <span className="spacer" />
        <span className="who">{displayName(session.player, session.guest)}</span>
        <button className="quiet" onClick={() => void session.leave()}>
          {session.guest ? "مغادرة" : "تسجيل الخروج"}
        </button>
      </header>
      {session.guest && <p className="guest-note">تقدّم الضيف لا يُحفظ. أنشئ حسابًا لتحتفظ به.</p>}
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}

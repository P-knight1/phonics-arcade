import { Link, Outlet } from "react-router-dom";
import { DEBUG } from "./debug";
import { useSession } from "./session";

export default function Layout() {
  const session = useSession();
  if (session.status !== "in") return null;

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          Phonics Arcade
        </Link>
        {DEBUG && <span className="badge">Debug</span>}
        <span className="spacer" />
        <span className="who">{session.player.name}</span>
        <button className="quiet" onClick={() => void session.leave()}>
          {session.guest ? "Leave" : "Log out"}
        </button>
      </header>
      {session.guest && <p className="guest-note">Guest progress isn't saved. Create an account to keep it.</p>}
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}

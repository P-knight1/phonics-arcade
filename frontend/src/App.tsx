import { Navigate, Route, Routes } from "react-router-dom";
import WordFlash from "./games/word-flash/WordFlash";
import AuthScreen from "./shell/AuthScreen";
import ComingSoon from "./shell/ComingSoon";
import Layout from "./shell/Layout";
import Menu from "./shell/Menu";
import { useSession } from "./shell/session";

export default function App() {
  const session = useSession();

  if (session.status === "loading") return <p className="center-note">Loading…</p>;
  if (session.status === "out") return <AuthScreen />;
  if (session.status === "offline") {
    return (
      <main className="auth">
        <p className="error" role="alert">
          Can't reach the server right now. Your login is kept.
        </p>
        <button className="primary" onClick={session.retry} autoFocus>
          Try again
        </button>
      </main>
    );
  }

  // Each game is its own page: replace a ComingSoon element with the real screen when it is ready.
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Menu />} />
        <Route path="games/word-flash" element={<WordFlash />} />
        <Route path="games/sound-surgery" element={<ComingSoon title="Sound Surgery" />} />
        <Route path="games/echo-chain" element={<ComingSoon title="Echo Chain" />} />
        <Route path="games/story-recall" element={<ComingSoon title="Story Recall" />} />
        <Route path="progress" element={<ComingSoon title="Progress" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

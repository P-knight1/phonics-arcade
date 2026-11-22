import { Navigate, Route, Routes } from "react-router-dom";
import Progress from "./games/progress/Progress";
import RhythmicReading from "./games/rhythmic-reading/RhythmicReading";
import SoundSurgery from "./games/sound-surgery/SoundSurgery";
import StoryRecall from "./games/story-recall/StoryRecall";
import WordFlash from "./games/word-flash/WordFlash";
import MicTest from "./tools/MicTest";
import AuthScreen from "./shell/AuthScreen";
import Layout from "./shell/Layout";
import Menu from "./shell/Menu";
import { useSession } from "./shell/session";

export default function App() {
  const session = useSession();

  if (session.status === "loading") return <p className="center-note">جارٍ التحميل…</p>;
  if (session.status === "out") return <AuthScreen />;
  if (session.status === "offline") {
    return (
      <main className="auth">
        <p className="error" role="alert">
          تعذّر الوصول إلى الخادم الآن. ما زلت مسجّل الدخول.
        </p>
        <button className="primary" onClick={session.retry} autoFocus>
          حاول مرة أخرى
        </button>
      </main>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Menu />} />
        <Route path="games/word-flash" element={<WordFlash />} />
        <Route path="games/sound-surgery" element={<SoundSurgery />} />
        <Route path="games/rhythmic-reading" element={<RhythmicReading />} />
        <Route path="games/story-recall" element={<StoryRecall />} />
        <Route path="progress" element={<Progress />} />
        <Route path="mic-test" element={<MicTest />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

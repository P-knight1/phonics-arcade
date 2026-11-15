import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../api";
import AnswerControls from "../../shell/AnswerControls";
import { FEEDBACK } from "../../shell/feedback";
import { BackLink } from "../../shell/round";
import { usePlayer } from "../../shell/session";
import { useScorer, type SpokenAnswer } from "../../shell/useScorer";

const GAME = "story_recall";
const TITLE = "قصتي";

type Phase = "loading" | "failed" | "intro" | "reading" | "feedback" | "questions";

/** One sentence per scored reading; /score takes up to 300 characters. */
function sentences(story: string): string[] {
  return story
    .split(/(?<=[.!؟?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function StoryRecall() {
  const player = usePlayer();
  const scorer = useScorer(GAME);
  const [phase, setPhase] = useState<Phase>("loading");
  const [story, setStory] = useState<api.Story | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<api.ScoreResult[]>([]);
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  const shownAt = useRef(0);

  const load = useCallback(async () => {
    setPhase("loading");
    try {
      setStory(await api.story(player.player_id));
      setIndex(0);
      setResults([]);
      setRevealed(new Set());
      setPhase("intro");
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 401) return;
      setError(
        e instanceof api.ApiError && e.status === 503
          ? "كتابة القصص غير متاحة الآن. جرّب لاحقًا."
          : "تعذّر تحميل القصة.",
      );
      setPhase("failed");
    }
  }, [player.player_id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (phase === "loading") return <p className="center-note">نكتب لك قصة…</p>;
  if (phase === "failed" || !story) {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="error" role="alert">
          {error}
        </p>
        <div className="row">
          <button className="primary" onClick={() => void load()}>
            حاول مرة أخرى
          </button>
          <BackLink />
        </div>
      </>
    );
  }

  const lines = sentences(story.story);
  const line = lines[index];
  const last = results[results.length - 1];

  function read(at: number) {
    setIndex(at);
    shownAt.current = Date.now();
    setPhase("reading");
  }

  async function submit(answer: SpokenAnswer) {
    const result = await scorer.check(line, answer, shownAt.current);
    if (result) {
      setResults((done) => [...done, result]);
      setPhase("feedback");
    }
  }

  if (phase === "intro") {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="lead">قصة كُتبت لك. اقرأها جملة جملة بصوت عالٍ، ثم أجب عن الأسئلة.</p>
        <div className="card story-text">{story.story}</div>
        <button className="primary" onClick={() => read(0)} autoFocus>
          ابدأ القراءة
        </button>
      </>
    );
  }

  if (phase === "questions") {
    const answered = results.filter((r) => r.error_type !== "no_response");
    const sounds = answered.length ? answered.reduce((sum, r) => sum + r.phoneme_accuracy, 0) / answered.length : 0;
    return (
      <>
        <h1>الأسئلة</h1>
        {answered.length > 0 && <p className="level">قرأت {Math.round(sounds * 100)}٪ من الأصوات صحيحة</p>}
        <div className="card story-text">{story.story}</div>
        {story.questions.map((q, i) => (
          <div key={i} className="card question">
            <p className="sentence">{q.q}</p>
            {revealed.has(i) ? (
              <p className="answer">{q.answer}</p>
            ) : (
              <button className="secondary" onClick={() => setRevealed((r) => new Set(r).add(i))}>
                أظهر الجواب
              </button>
            )}
          </div>
        ))}
        <div className="row">
          <button className="primary" onClick={() => void load()}>
            قصة جديدة
          </button>
          <BackLink />
        </div>
      </>
    );
  }

  const count = (
    <p className="count">
      الجملة {index + 1} من {lines.length}
    </p>
  );

  if (phase === "feedback" && last) {
    const isLast = index + 1 >= lines.length;
    return (
      <>
        {count}
        <div className={last.correct ? "stage correct" : "stage wrong"}>
          <p className="sentence">{line}</p>
          <p className="verdict">
            {last.correct ? "✓ قرأتها كلها صحيحة!" : `${Math.round(last.phoneme_accuracy * 100)}٪ من الأصوات صحيحة`}
          </p>
          {!last.correct && <p>{FEEDBACK[last.error_type]}</p>}
        </div>
        <button className="primary" onClick={() => (isLast ? setPhase("questions") : read(index + 1))} autoFocus>
          {isLast ? "إلى الأسئلة" : "الجملة التالية"}
        </button>
      </>
    );
  }

  return (
    <>
      {count}
      <div className="stage">
        <p className="sentence">{line}</p>
      </div>
      <AnswerControls scorer={scorer} target={line} onAnswer={(a) => void submit(a)} skipLabel="تخطَّ الجملة" />
    </>
  );
}

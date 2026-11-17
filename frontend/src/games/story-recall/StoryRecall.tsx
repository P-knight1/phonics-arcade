import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../api";
import AnswerControls from "../../shell/AnswerControls";
import CoachNote from "../../shell/CoachNote";
import { FEEDBACK } from "../../shell/feedback";
import { BackLink } from "../../shell/round";
import { usePlayer } from "../../shell/session";
import { useScorer, type SpokenAnswer } from "../../shell/useScorer";

const GAME = "story_recall";
const TITLE = "قصتي";
const READINGS = 3; // repeated reading: the same text read up to three times, with feedback each time

type Phase = "loading" | "locked" | "failed" | "intro" | "reading" | "feedback" | "between" | "questions";

/** One sentence per scored reading; /score takes up to 300 characters. */
function sentences(story: string): string[] {
  return story
    .split(/(?<=[.!؟?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

interface Reading {
  results: api.Attempt[];
  seconds: number;
}

/** Share of sounds read right, over the sentences actually read. */
function soundShare(results: api.Attempt[]): number | null {
  const read = results.filter((r) => r.error_type !== "no_response");
  return read.length ? read.reduce((sum, r) => sum + r.phoneme_accuracy, 0) / read.length : null;
}

function ReadingsTable({ readings }: { readings: Reading[] }) {
  return (
    <div className="card">
      {readings.map((r, i) => {
        const share = soundShare(r.results);
        return (
          <div key={i} className="reading-row">
            <span>القراءة {i + 1}</span>
            <span>{share === null ? "—" : `${Math.round(share * 100)}٪ أصوات صحيحة`}</span>
            <span>{Math.round(r.seconds)} ث</span>
          </div>
        );
      })}
    </div>
  );
}

export default function StoryRecall() {
  const player = usePlayer();
  const scorer = useScorer(GAME);
  const [phase, setPhase] = useState<Phase>("loading");
  const [status, setStatus] = useState<{ attempts: number; needed: number } | null>(null);
  const [story, setStory] = useState<api.Story | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [readings, setReadings] = useState<Reading[]>([]);
  const [current, setCurrent] = useState<api.Attempt[]>([]);
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  const shownAt = useRef(0);
  const readingStarted = useRef(0);

  const load = useCallback(async () => {
    setPhase("loading");
    try {
      const s = await api.storyStatus(player.player_id);
      if (!s.unlocked) {
        setStatus(s);
        setPhase("locked");
        return;
      }
      setStory(await api.story(player.player_id));
      setReadings([]);
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

  if (phase === "loading") return <p className="center-note">نكتب لك قصة من كلماتك…</p>;
  if (phase === "locked" && status) {
    const left = status.needed - status.attempts;
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="lead">
          القصة تُكتب لك من الحروف والكلمات التي تتدرّب عليها. العب قليلًا أولًا حتى نعرفها.
        </p>
        <div className="bar" role="img" aria-label={`${status.attempts} من ${status.needed}`}>
          <span style={{ width: `${(status.attempts / status.needed) * 100}%` }} />
        </div>
        <p className="spaced">
          بقي {left === 1 ? "كلمة واحدة" : left === 2 ? "كلمتان" : `${left} ${left <= 10 ? "كلمات" : "كلمة"}`} في
          الألعاب الأخرى لتُفتح قصتك.
        </p>
        <BackLink />
      </>
    );
  }
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
  const last = current[current.length - 1];
  const round = readings.length + 1;

  function read(at: number) {
    setIndex(at);
    shownAt.current = Date.now();
    setPhase("reading");
  }

  function startReading() {
    setCurrent([]);
    readingStarted.current = Date.now();
    read(0);
  }

  function endReading() {
    const done = [...readings, { results: current, seconds: (Date.now() - readingStarted.current) / 1000 }];
    setReadings(done);
    setPhase(done.length >= READINGS ? "questions" : "between");
  }

  async function submit(answer: SpokenAnswer) {
    const result = await scorer.check(line, answer, shownAt.current);
    if (result) {
      setCurrent((done) => [...done, { ...result, target: line }]);
      setPhase("feedback");
    }
  }

  if (phase === "intro") {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="lead">
          قصة كُتبت لك من الحروف والكلمات التي تتدرّب عليها. ستقرؤها حتى {READINGS} مرات، جملة جملة، وفي كل مرة تصبح
          أسهل.
        </p>
        <div className="card story-text">{story.story}</div>
        <button className="primary" onClick={startReading} autoFocus>
          ابدأ القراءة
        </button>
      </>
    );
  }

  if (phase === "between") {
    return (
      <>
        <h1>أحسنت!</h1>
        <p className="lead">القراءة مرة أخرى تجعلها أسرع وأدق.</p>
        <ReadingsTable readings={readings} />
        <CoachNote kind="round" attempts={readings[readings.length - 1].results} />
        <div className="row">
          <button className="primary" onClick={startReading} autoFocus>
            اقرأها مرة أخرى ({round} من {READINGS})
          </button>
          <button className="secondary" onClick={() => setPhase("questions")}>
            إلى الأسئلة
          </button>
        </div>
      </>
    );
  }

  if (phase === "questions") {
    return (
      <>
        <h1>الأسئلة</h1>
        <ReadingsTable readings={readings} />
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
      القراءة {round} من {READINGS} · الجملة {index + 1} من {lines.length}
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
        {!last.correct && last.error_type !== "no_response" && <CoachNote kind="word" attempts={[last]} />}
        <button className="primary" onClick={() => (isLast ? endReading() : read(index + 1))} autoFocus>
          {isLast ? "أنهِ القراءة" : "الجملة التالية"}
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

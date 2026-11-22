import { useEffect, useRef, useState } from "react";
import type * as api from "../../api";
import AnswerControls from "../../shell/AnswerControls";
import CoachNote from "../../shell/CoachNote";
import { FEEDBACK } from "../../shell/feedback";
import { RoundFailed, RoundSummary, useRound } from "../../shell/round";
import { useScorer, type SpokenAnswer } from "../../shell/useScorer";

const GAME = "word_flash";
const TITLE = "الكلمة الخاطفة";

type Phase = "intro" | "showing" | "answering" | "feedback" | "summary";

export default function WordFlash() {
  const round = useRound(GAME);
  const scorer = useScorer(GAME);
  const [phase, setPhase] = useState<Phase>("intro");
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<api.Attempt[]>([]);
  const shownAt = useRef(0);
  const exercise = round.exercise;

  // The word hides after display_ms. The player can still answer once it is gone.
  useEffect(() => {
    if (phase !== "showing" || !exercise) return;
    const timer = setTimeout(() => setPhase("answering"), exercise.display_ms);
    return () => clearTimeout(timer);
  }, [phase, exercise, index]);

  function newRound(history: api.ScoreResult[]) {
    setIndex(0);
    setResults([]);
    setPhase("intro");
    void round.load(history);
  }

  if (round.state === "loading") return <p className="center-note">جارٍ التحميل…</p>;
  if (round.state === "failed" || !exercise) {
    return <RoundFailed title={TITLE} error={round.error} retry={() => newRound([])} />;
  }

  const word = exercise.items[index];
  const last = results[results.length - 1];

  function showWord(at: number) {
    setIndex(at);
    shownAt.current = Date.now();
    setPhase("showing");
  }

  async function submit(answer: SpokenAnswer) {
    const result = await scorer.check(word, answer, shownAt.current);
    if (result) {
      setResults((done) => [...done, { ...result, target: word }]);
      setPhase("feedback");
    } else {
      setPhase("answering");
    }
  }

  if (phase === "intro") {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="level">المستوى {exercise.level}</p>
        <p className="lead">{exercise.reason}</p>
        <p>
          {exercise.items.length} كلمات. تظهر كل كلمة {(exercise.display_ms / 1000).toFixed(1)} ثانية ثم تختفي. اقرأها
          بصوت عالٍ.
        </p>
        <button className="primary" onClick={() => showWord(0)} autoFocus>
          ابدأ
        </button>
      </>
    );
  }

  if (phase === "summary") return <RoundSummary results={results} next={() => newRound(results)} />;

  const count = (
    <p className="count">
      الكلمة {index + 1} من {exercise.items.length}
    </p>
  );

  if (phase === "feedback" && last) {
    const isLast = index + 1 >= exercise.items.length;
    return (
      <>
        {count}
        <div className={last.correct ? "stage correct" : "stage wrong"}>
          <p className="word">{word}</p>
          <p className="verdict">{last.correct ? "✓ أحسنت!" : "هذه هي الكلمة."}</p>
          {!last.correct && last.heard && <p>سمعنا: {last.heard}</p>}
          {!last.correct && <p>{FEEDBACK[last.error_type]}</p>}
        </div>
        {!last.correct && last.error_type !== "no_response" && <CoachNote kind="word" attempts={[last]} />}
        <button className="primary" onClick={() => (isLast ? setPhase("summary") : showWord(index + 1))} autoFocus>
          {isLast ? "أنهِ الجولة" : "الكلمة التالية"}
        </button>
      </>
    );
  }

  return (
    <>
      {count}
      <div className="stage">
        {phase === "showing" ? <p className="word">{word}</p> : <p className="hidden-word">ما الكلمة؟</p>}
      </div>
      <AnswerControls scorer={scorer} target={word} onAnswer={(answer) => void submit(answer)} />
    </>
  );
}

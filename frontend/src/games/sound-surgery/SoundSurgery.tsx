import { useRef, useState } from "react";
import type * as api from "../../api";
import AnswerControls from "../../shell/AnswerControls";
import CoachNote from "../../shell/CoachNote";
import { FEEDBACK } from "../../shell/feedback";
import { RoundFailed, RoundSummary, useRound } from "../../shell/round";
import { useScorer, type SpokenAnswer } from "../../shell/useScorer";

const GAME = "sound_surgery";
const TITLE = "جراحة الأصوات";

type Phase = "intro" | "asking" | "feedback" | "summary";

/** Items are "prompt|answer" (content/sound_surgery.json); a plain word is its own prompt and answer. */
function split(item: string): { prompt: string; answer: string } {
  const [prompt, answer = prompt] = item.split("|");
  return { prompt, answer };
}

export default function SoundSurgery() {
  const round = useRound(GAME);
  const scorer = useScorer(GAME);
  const [phase, setPhase] = useState<Phase>("intro");
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<api.Attempt[]>([]);
  const shownAt = useRef(0);
  const exercise = round.exercise;

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

  const { prompt, answer } = split(exercise.items[index]);
  const last = results[results.length - 1];

  function ask(at: number) {
    setIndex(at);
    shownAt.current = Date.now();
    setPhase("asking");
  }

  async function submit(spoken: SpokenAnswer) {
    const result = await scorer.check(answer, spoken, shownAt.current);
    if (result) {
      setResults((done) => [...done, { ...result, target: answer }]);
      setPhase("feedback");
    }
  }

  if (phase === "intro") {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="level">المستوى {exercise.level}</p>
        <p className="lead">{exercise.reason}</p>
        <p>اقرأ ما يُطلب منك في كل بطاقة، ثم قل الكلمة الجديدة بصوت عالٍ. لا بأس إن كانت الكلمة بلا معنى.</p>
        <button className="primary" onClick={() => ask(0)} autoFocus>
          ابدأ
        </button>
      </>
    );
  }

  if (phase === "summary") return <RoundSummary results={results} next={() => newRound(results)} />;

  const count = (
    <p className="count">
      البطاقة {index + 1} من {exercise.items.length}
    </p>
  );

  if (phase === "feedback" && last) {
    const isLast = index + 1 >= exercise.items.length;
    // Saying the whole word again is the usual slip in deletion tasks.
    const wholeWord = last.error_type === "added_sound";
    return (
      <>
        {count}
        <div className={last.correct ? "stage correct" : "stage wrong"}>
          <p className="prompt">{prompt}</p>
          <p className="verdict">{last.correct ? "✓ أحسنت!" : "الجواب:"}</p>
          {!last.correct && <p className="word">{answer}</p>}
          {!last.correct && (
            <p>{wholeWord ? "يبدو أنك قلت الكلمة كاملة. احذف الصوت ثم قلها." : FEEDBACK[last.error_type]}</p>
          )}
        </div>
        {!last.correct && last.error_type !== "no_response" && <CoachNote kind="word" attempts={[last]} />}
        <button className="primary" onClick={() => (isLast ? setPhase("summary") : ask(index + 1))} autoFocus>
          {isLast ? "أنهِ الجولة" : "البطاقة التالية"}
        </button>
      </>
    );
  }

  return (
    <>
      {count}
      <div className="stage">
        <p className="prompt">{prompt}</p>
      </div>
      <AnswerControls scorer={scorer} target={answer} onAnswer={(spoken) => void submit(spoken)} skipLabel="تخطَّ" />
    </>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../../api";
import { DEBUG } from "../../shell/debug";
import DebugPanel from "../../shell/DebugPanel";
import { FEEDBACK } from "../../shell/feedback";
import MicButton from "../../shell/MicButton";
import { usePlayer } from "../../shell/session";
import { useRecorder } from "../../shell/useRecorder";

const GAME = "word_flash";

type Phase =
  | "loading" // asking the server for the next round
  | "ready" // round intro: level and reason
  | "showing" // the word is on screen
  | "answering" // the word is hidden, waiting for the answer
  | "scoring"
  | "feedback"
  | "summary" // round finished
  | "failed"; // the round could not be loaded

export default function WordFlash() {
  const player = usePlayer();
  const recorder = useRecorder();
  const [phase, setPhase] = useState<Phase>("loading");
  const [exercise, setExercise] = useState<api.Exercise | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<api.ScoreResult[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  // Voice scoring answered 503 (model not connected): fall back to the debug buttons.
  const [voiceDown, setVoiceDown] = useState(false);
  const shownAt = useRef(0);

  const loadRound = useCallback(
    async (history: api.ScoreResult[]) => {
      setPhase("loading");
      setNotice(null);
      try {
        setExercise(await api.nextExercise(player.player_id, GAME, history));
        setIndex(0);
        setResults([]);
        setPhase("ready");
      } catch (e) {
        if (e instanceof api.ApiError && e.status === 401) return; // the shell shows the login screen
        setNotice(
          e instanceof api.ApiError && e.status === 404
            ? "There are no words for this game yet."
            : "The round could not be loaded.",
        );
        setPhase("failed");
      }
    },
    [player.player_id],
  );

  useEffect(() => {
    void loadRound([]);
  }, [loadRound]);

  // The word hides after display_ms. The player can still answer once it is gone.
  useEffect(() => {
    if (phase !== "showing" || !exercise) return;
    const timer = setTimeout(() => setPhase("answering"), exercise.display_ms);
    return () => clearTimeout(timer);
  }, [phase, exercise, index]);

  if (phase === "loading") return <p className="center-note">Loading…</p>;
  if (phase === "failed" || !exercise) {
    return (
      <>
        <h1>Word Flash</h1>
        <p className="error" role="alert">
          {notice}
        </p>
        <div className="row">
          <button className="primary" onClick={() => void loadRound([])}>
            Try again
          </button>
          <Link to="/" className="button secondary">
            Back to games
          </Link>
        </div>
      </>
    );
  }

  const word = exercise.items[index];
  const last = results[results.length - 1];

  function showWord(at: number) {
    setIndex(at);
    setNotice(null);
    shownAt.current = Date.now();
    setPhase("showing");
  }

  async function submit(answer: { audio?: Blob; heardText?: string }) {
    recorder.cancel();
    setPhase("scoring");
    setNotice(null);
    try {
      const result = await api.score({ target: word, game: GAME, shownAtMs: shownAt.current, ...answer });
      setResults((done) => [...done, result]);
      setPhase("feedback");
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 401) return;
      if (e instanceof api.ApiError && e.status === 503) {
        setVoiceDown(true);
        setNotice("Voice scoring is not connected yet. Use the buttons below.");
      } else {
        setNotice("That answer could not be checked. Try again.");
      }
      setPhase("answering");
    }
  }

  if (phase === "ready") {
    return (
      <>
        <h1>Word Flash</h1>
        <p className="level">Level {exercise.level}</p>
        <p className="lead">{exercise.reason}</p>
        <p>
          {exercise.items.length} words. Each word shows for {(exercise.display_ms / 1000).toFixed(1)} seconds, then
          hides. Say it out loud.
        </p>
        <button className="primary" onClick={() => showWord(0)} autoFocus>
          Start
        </button>
      </>
    );
  }

  if (phase === "summary") {
    const right = results.filter((r) => r.correct).length;
    return (
      <>
        <h1>Round done</h1>
        <p className="level">
          {right} of {results.length} right
        </p>
        <div className="row">
          <button className="primary" onClick={() => void loadRound(results)} autoFocus>
            Next round
          </button>
          <Link to="/" className="button secondary">
            Back to games
          </Link>
        </div>
      </>
    );
  }

  const count = (
    <p className="count">
      Word {index + 1} of {exercise.items.length}
    </p>
  );

  if (phase === "feedback" && last) {
    const isLast = index + 1 >= exercise.items.length;
    return (
      <>
        {count}
        <div className={last.correct ? "stage correct" : "stage wrong"}>
          <p className="word">{word}</p>
          <p className="verdict">{last.correct ? "✓ You got it!" : `The word was ${word}.`}</p>
          {!last.correct && last.heard && <p>You said {last.heard}.</p>}
          {!last.correct && <p>{FEEDBACK[last.error_type]}</p>}
        </div>
        <button className="primary" onClick={() => (isLast ? setPhase("summary") : showWord(index + 1))} autoFocus>
          {isLast ? "Finish round" : "Next word"}
        </button>
      </>
    );
  }

  const busy = phase === "scoring";
  return (
    <>
      {count}
      <div className="stage">
        {phase === "showing" ? <p className="word">{word}</p> : <p className="hidden-word">What was the word?</p>}
      </div>
      {notice && (
        <p className="error" role="alert">
          {notice}
        </p>
      )}
      {busy ? (
        <p className="center-note">Checking…</p>
      ) : (
        <>
          {!voiceDown && <MicButton recorder={recorder} onAudio={(audio) => void submit({ audio })} />}
          <button className="quiet" onClick={() => void submit({})}>
            I missed it
          </button>
          {(DEBUG || voiceDown || !recorder.supported) && (
            <DebugPanel target={word} onAnswer={(heardText) => void submit({ heardText })} />
          )}
        </>
      )}
    </>
  );
}

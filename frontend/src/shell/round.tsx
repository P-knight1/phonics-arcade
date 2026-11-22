import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../api";
import CoachNote from "./CoachNote";
import { usePlayer } from "./session";

/** One round of a word-list game: the server picks the level and items from the last round's results. */
export function useRound(game: string) {
  const player = usePlayer();
  const [exercise, setExercise] = useState<api.Exercise | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [error, setError] = useState("");

  const load = useCallback(
    async (history: api.ScoreResult[]) => {
      setState("loading");
      try {
        setExercise(await api.nextExercise(player.player_id, game, history));
        setState("ready");
      } catch (e) {
        if (e instanceof api.ApiError && e.status === 401) return; // the shell shows the login screen
        setError(
          e instanceof api.ApiError && e.status === 404 ? "لا توجد كلمات لهذه اللعبة بعد." : "تعذّر تحميل الجولة.",
        );
        setState("failed");
      }
    },
    [player.player_id, game],
  );

  useEffect(() => {
    void load([]);
  }, [load]);

  return { exercise, state, error, load };
}

export function BackLink() {
  return (
    <Link to="/" className="button secondary">
      العودة إلى الألعاب
    </Link>
  );
}

export function RoundFailed({ title, error, retry }: { title: string; error: string; retry(): void }) {
  return (
    <>
      <h1>{title}</h1>
      <p className="error" role="alert">
        {error}
      </p>
      <div className="row">
        <button className="primary" onClick={retry}>
          حاول مرة أخرى
        </button>
        <BackLink />
      </div>
    </>
  );
}

export function RoundSummary({ results, next }: { results: api.Attempt[]; next(): void }) {
  const right = results.filter((r) => r.correct).length;
  return (
    <>
      <h1>انتهت الجولة</h1>
      <p className="level">
        {right} من {results.length} صحيحة
      </p>
      <CoachNote kind="round" attempts={results} />
      <div className="row">
        <button className="primary" onClick={next} autoFocus>
          الجولة التالية
        </button>
        <BackLink />
      </div>
    </>
  );
}

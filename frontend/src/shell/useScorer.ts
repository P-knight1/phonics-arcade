import { useRef, useState } from "react";
import * as api from "../api";
import { useRecorder } from "./useRecorder";

export interface SpokenAnswer {
  /** Mic answer. */
  audio?: Blob;
  /** Typed answer (debug mode). Leave both out when the player said nothing. */
  heardText?: string;
}

/** Scoring for one game screen: the mic, a busy flag, a message for the player, and the fallback to typed answers. */
export function useScorer(game: string) {
  const recorder = useRecorder();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  // /score answered 503: the speech model isn't available, so the typed-answer buttons take over.
  const [voiceDown, setVoiceDown] = useState(false);
  // The word whose last reading was unclear: its next reading is the second try, which always gets a verdict.
  const unclearTarget = useRef<string | null>(null);

  /** Null when the answer couldn't be scored or needs another reading; `notice` then says why. */
  async function check(target: string, answer: SpokenAnswer, shownAtMs?: number): Promise<api.ScoreResult | null> {
    recorder.cancel();
    setBusy(true);
    setNotice(null);
    try {
      const secondTry = unclearTarget.current === target;
      const result = await api.score({ target, game, shownAtMs, secondTry, ...answer });
      if (result.unclear) {
        unclearTarget.current = target;
        setNotice("لم نسمعها جيدًا. اقرأها مرة أخرى بصوت واضح.");
        return null;
      }
      unclearTarget.current = null;
      return result;
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 503) {
        setVoiceDown(true);
        setNotice("التصحيح بالصوت غير متاح الآن. استخدم الأزرار في الأسفل.");
      } else if (!(e instanceof api.ApiError && e.status === 401)) {
        setNotice("لم نتمكن من تصحيح الإجابة. حاول مرة أخرى.");
      }
      return null;
    } finally {
      setBusy(false);
    }
  }

  return { recorder, busy, notice, voiceDown, check };
}

export type Scorer = ReturnType<typeof useScorer>;

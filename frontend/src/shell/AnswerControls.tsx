import DebugPanel from "./DebugPanel";
import { DEBUG } from "./debug";
import MicButton from "./MicButton";
import type { Scorer, SpokenAnswer } from "./useScorer";

interface Props {
  scorer: Scorer;
  /** What the player should say. */
  target: string;
  onAnswer(answer: SpokenAnswer): void;
  /** The no-answer button. */
  skipLabel?: string;
}

/** The answer area every game shares: mic, a no-answer button, and typed answers when needed. */
export default function AnswerControls({ scorer, target, onAnswer, skipLabel = "فاتتني" }: Props) {
  const { recorder, busy, notice, voiceDown } = scorer;
  return (
    <>
      {notice && (
        <p className="error" role="alert">
          {notice}
        </p>
      )}
      {busy ? (
        <p className="center-note">جارٍ التصحيح…</p>
      ) : (
        <>
          {!voiceDown && <MicButton recorder={recorder} onAudio={(audio) => onAnswer({ audio })} />}
          <button className="quiet" onClick={() => onAnswer({})}>
            {skipLabel}
          </button>
          {(DEBUG || voiceDown || !recorder.supported) && (
            <DebugPanel target={target} onAnswer={(heardText) => onAnswer({ heardText })} />
          )}
        </>
      )}
    </>
  );
}

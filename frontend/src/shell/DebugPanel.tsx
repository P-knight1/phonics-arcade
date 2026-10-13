import { useState } from "react";

interface Props {
  /** What the player should say. */
  target: string;
  /** Called with the text to score in place of audio. */
  onAnswer(heardText: string): void;
  disabled?: boolean;
}

/** Placeholder input: answer without a microphone, so games stay playable when the AI is down. */
export default function DebugPanel({ target, onAnswer, disabled }: Props) {
  const [typed, setTyped] = useState("");

  function answer(text: string) {
    setTyped("");
    onAnswer(text);
  }

  return (
    <div className="debug-panel">
      <p className="debug-title">Debug answers</p>
      <div className="row">
        <button className="secondary" onClick={() => answer(target)} disabled={disabled}>
          ✓ Said it right
        </button>
        {/* "Wrong" needs to know what was heard; "I missed it" is the no-answer button. */}
        <button className="secondary" onClick={() => answer(typed.trim())} disabled={disabled || !typed.trim()}>
          ✗ Said it wrong
        </button>
      </div>
      <label>
        What was heard
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="bog" disabled={disabled} />
      </label>
    </div>
  );
}

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
      <p className="debug-title">إجابات التجربة</p>
      <div className="row">
        <button className="secondary" onClick={() => answer(target)} disabled={disabled}>
          ✓ قالها صحيحة
        </button>
        {/* "Wrong" needs to know what was heard; the skip button is the no-answer case. */}
        <button className="secondary" onClick={() => answer(typed.trim())} disabled={disabled || !typed.trim()}>
          ✗ قالها خطأ
        </button>
      </div>
      <label>
        ما الذي سُمع (بالتشكيل)
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="جَبْلْ" disabled={disabled} />
      </label>
    </div>
  );
}

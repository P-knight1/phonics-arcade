import type { Recorder } from "./useRecorder";

interface Props {
  recorder: Recorder;
  /** Called with the recording when the player taps to finish. */
  onAudio(audio: Blob): void;
  disabled?: boolean;
}

/** Tap to start speaking, tap again when done. */
export default function MicButton({ recorder, onAudio, disabled }: Props) {
  async function toggle() {
    if (!recorder.recording) {
      await recorder.start();
      return;
    }
    const audio = await recorder.stop();
    if (audio) onAudio(audio);
  }

  return (
    <div className="mic">
      <button
        className={recorder.recording ? "mic-button recording" : "mic-button"}
        onClick={() => void toggle()}
        disabled={disabled || !recorder.supported}
        aria-pressed={recorder.recording}
      >
        {recorder.recording ? "انتهيت" : "تكلّم"}
      </button>
      <p className="hint">
        {recorder.recording ? "نستمع إليك. اضغط «انتهيت» بعد أن تقولها." : "اضغط «تكلّم» ثم قلها بصوت عالٍ."}
      </p>
      {recorder.error && (
        <p className="error" role="alert">
          {recorder.error}
        </p>
      )}
    </div>
  );
}

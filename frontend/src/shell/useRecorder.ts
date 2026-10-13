import { useCallback, useEffect, useRef, useState } from "react";

export interface Recorder {
  /** False when the browser has no microphone recording at all. */
  supported: boolean;
  recording: boolean;
  /** Why recording could not start, in words for the player. */
  error: string | null;
  /** Asks for the microphone on first use. Resolves false when it could not start. */
  start(): Promise<boolean>;
  /** Ends the recording and returns it (webm, or mp4 on Safari). Null when nothing was recording. */
  stop(): Promise<Blob | null>;
  /** Ends the recording and throws it away. */
  cancel(): void;
}

/** One microphone recorder for a game screen. The mic stays open between answers, so there is one permission prompt. */
export function useRecorder(): Recorder {
  const supported = typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);

  const start = useCallback(async () => {
    if (!supported) {
      setError("This browser can't record sound.");
      return false;
    }
    if (recorder.current) return true;
    try {
      stream.current ??= await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("The microphone is blocked. Allow it in your browser, then try again.");
      return false;
    }
    setError(null);
    recorder.current = new MediaRecorder(stream.current);
    recorder.current.start();
    setRecording(true);
    return true;
  }, [supported]);

  const stop = useCallback(() => {
    const active = recorder.current;
    if (!active) return Promise.resolve(null);
    recorder.current = null;
    setRecording(false);
    return new Promise<Blob | null>((resolve) => {
      const chunks: Blob[] = [];
      active.ondataavailable = (e) => chunks.push(e.data);
      active.onstop = () => resolve(new Blob(chunks, { type: active.mimeType }));
      active.stop();
    });
  }, []);

  const cancel = useCallback(() => void stop(), [stop]);

  // Leaving the screen: stop recording and release the microphone.
  useEffect(
    () => () => {
      recorder.current?.stop();
      recorder.current = null;
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
    },
    [],
  );

  return { supported, recording, error, start, stop, cancel };
}

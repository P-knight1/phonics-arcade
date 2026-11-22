import { useEffect, useRef, useState } from "react";
import * as api from "../../api";
import CoachNote from "../../shell/CoachNote";
import DebugPanel from "../../shell/DebugPanel";
import { DEBUG } from "../../shell/debug";
import { FEEDBACK } from "../../shell/feedback";
import { BackLink, RoundFailed, useRound } from "../../shell/round";
import { useRecorder } from "../../shell/useRecorder";

const GAME = "rhythmic_reading";
const TITLE = "القراءة على الإيقاع";
const COUNT_IN = 4; // beats before the first word
const BEATS_PER_WORD = 2; // the word shows on the first beat and hides on the second

type Phase = "intro" | "running" | "typed" | "checking" | "results";

/** A short tick from the Web Audio API; the browser's echo cancellation keeps it out of the recording. */
function tick(ctx: AudioContext, accent: boolean) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.frequency.value = accent ? 1320 : 880;
  gain.gain.setValueAtTime(0.15, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.06);
}

function timing(word: api.RhythmWord): string {
  if (word.on_time === null) return "";
  if (word.on_time) return "في الوقت";
  return (word.offset_ms ?? 0) < 0 ? "مبكرًا" : "متأخرًا";
}

export default function RhythmicReading() {
  const round = useRound(GAME);
  const recorder = useRecorder();
  const [phase, setPhase] = useState<Phase>("intro");
  const [beat, setBeat] = useState(-1);
  const [sound, setSound] = useState(true);
  const [result, setResult] = useState<api.RhythmResult | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceDown, setVoiceDown] = useState(false);
  const recording = useRef<Blob | null>(null);
  const startedAt = useRef(0);
  const audioCtx = useRef<AudioContext | null>(null);
  const exercise = round.exercise;
  const beatMs = (exercise?.display_ms ?? 2000) / BEATS_PER_WORD;
  const items = exercise?.items ?? [];

  // The beat clock: a 20 ms timer that reads performance.now(), so beats never drift even if a tick runs late.
  useEffect(() => {
    if (phase !== "running") return;
    const total = COUNT_IN + items.length * BEATS_PER_WORD;
    let last = -1;
    const timer = setInterval(() => {
      const b = Math.floor((performance.now() - startedAt.current) / beatMs);
      if (b === last) return;
      last = b;
      if (b >= total) {
        clearInterval(timer);
        void finish();
        return;
      }
      setBeat(b);
      if (audioCtx.current) tick(audioCtx.current, b >= COUNT_IN && (b - COUNT_IN) % BEATS_PER_WORD === 0);
    }, 20);
    return () => clearInterval(timer);
    // finish only reads refs and the recorder, which stay the same for the whole run
  }, [phase, beatMs, items.length]);

  if (round.state === "loading") return <p className="center-note">جارٍ التحميل…</p>;
  if (round.state === "failed" || !exercise) {
    return <RoundFailed title={TITLE} error={round.error} retry={() => void round.load([])} />;
  }

  async function start() {
    setNotice(null);
    setResult(null);
    recording.current = null;
    if (!voiceDown) await recorder.start(); // no mic: the run still plays, then the answer is typed
    if (sound) {
      audioCtx.current ??= new AudioContext();
      void audioCtx.current.resume();
    }
    startedAt.current = performance.now();
    setBeat(-1);
    setPhase("running");
  }

  async function finish() {
    recording.current = await recorder.stop();
    if (recording.current && !DEBUG) void submit({ audio: recording.current });
    else setPhase("typed");
  }

  async function submit(answer: { audio?: Blob; heardText?: string }) {
    setPhase("checking");
    setNotice(null);
    try {
      setResult(
        await api.scoreRhythm({ targets: items, slotMs: beatMs * BEATS_PER_WORD, firstWordMs: COUNT_IN * beatMs, ...answer }),
      );
      setPhase("results");
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 401) return;
      if (e instanceof api.ApiError && e.status === 503) {
        setVoiceDown(true);
        setNotice("التصحيح بالصوت غير متاح الآن. اكتب ما قرأته في الأسفل.");
      } else {
        setNotice("لم نتمكن من تصحيح القراءة. اكتبها في الأسفل أو أعد المحاولة.");
      }
      setPhase("typed");
    }
  }

  function nextRound() {
    setPhase("intro");
    void round.load(result?.words ?? []);
  }

  if (phase === "intro") {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="level">المستوى {exercise.level}</p>
        <p className="lead">{exercise.reason}</p>
        <p>
          اضغط «ابدأ» ثم استمع إلى الإيقاع. بعد أربع نبضات تظهر الكلمات واحدة تلو الأخرى. اقرأ كل كلمة بصوت عالٍ مع
          الإيقاع، دون أن تتوقف. الميكروفون يسجّل الجولة كلها مرة واحدة.
        </p>
        <label className="check">
          <input type="checkbox" checked={sound} onChange={(e) => setSound(e.target.checked)} />
          صوت الإيقاع (يُفضَّل مع سماعات)
        </label>
        {recorder.error && (
          <p className="error" role="alert">
            {recorder.error}
          </p>
        )}
        <button className="primary" onClick={() => void start()} autoFocus>
          ابدأ
        </button>
      </>
    );
  }

  if (phase === "running") {
    const counting = beat < COUNT_IN;
    const step = beat - COUNT_IN;
    const index = Math.floor(step / BEATS_PER_WORD);
    const visible = !counting && step % BEATS_PER_WORD === 0;
    return (
      <>
        <p className="count">{counting ? "استعد…" : `الكلمة ${index + 1} من ${items.length}`}</p>
        <div className="stage">
          <span key={beat} className={beat >= 0 ? "pulse beat" : "pulse"} aria-hidden="true" />
          {counting ? (
            <p className="word">{beat >= 0 ? COUNT_IN - beat : ""}</p>
          ) : (
            <p className="word">{visible ? items[index] : " "}</p>
          )}
        </div>
        <p className="center-note">{recorder.recording ? "🎙 نسجّل…" : "بلا تسجيل: ستكتب ما قرأته بعد الجولة"}</p>
      </>
    );
  }

  if (phase === "checking") return <p className="center-note">جارٍ التصحيح…</p>;

  if (phase === "typed") {
    return (
      <>
        <h1>{TITLE}</h1>
        {notice && (
          <p className="error" role="alert">
            {notice}
          </p>
        )}
        <p>الكلمات كانت: {items.join("، ")}</p>
        {recording.current && !voiceDown && (
          <button className="primary" onClick={() => void submit({ audio: recording.current! })}>
            صحّح التسجيل
          </button>
        )}
        <DebugPanel target={items.join(" ")} onAnswer={(heardText) => void submit({ heardText })} />
        <div className="row spaced">
          <button className="secondary" onClick={() => void start()}>
            أعد الجولة
          </button>
          <BackLink />
        </div>
      </>
    );
  }

  // results
  const words = result?.words ?? [];
  const right = words.filter((w) => w.correct).length;
  const onTime = words.filter((w) => w.on_time).length;
  const timed = words.some((w) => w.on_time !== null);
  return (
    <>
      <h1>انتهت الجولة</h1>
      <p className="level">
        {right} من {words.length} صحيحة{timed && ` · ${onTime} في الوقت`}
      </p>
      {result?.steadiness_ms != null && (
        <p className="lead">
          {result.steadiness_ms <= beatMs / 2 ? "إيقاعك ثابت. أحسنت!" : "حاول أن تبقى مع الإيقاع: كلمة مع كل ظهور."}
        </p>
      )}
      <div className="card">
        {words.map((w, i) => (
          <div key={i} className={w.correct ? "rhythm-row correct" : "rhythm-row wrong"}>
            <span className="rhythm-word">{w.target}</span>
            <span>{w.correct ? "✓" : FEEDBACK[w.error_type]}</span>
            <span className="rhythm-time">{timing(w)}</span>
          </div>
        ))}
      </div>
      <CoachNote kind="round" attempts={words} />
      <div className="row">
        <button className="primary" onClick={nextRound} autoFocus>
          الجولة التالية
        </button>
        <button className="secondary" onClick={() => void start()}>
          أعد الجولة
        </button>
        <BackLink />
      </div>
    </>
  );
}

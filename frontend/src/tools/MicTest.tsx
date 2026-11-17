import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../api";
import { FEEDBACK } from "../shell/feedback";
import { useRecorder } from "../shell/useRecorder";

// Mic check, not a game and not in the menu: open /mic-test. Two modes:
// «با»: say «با» on every beat; compares when the model heard each «ب» with when the beat played.
// words: real words shown like Rhythmic Reading (one per two beats); shows what the model heard, as Arabic, and
// each word's result and timing. Both start the clock exactly like the game does. Nothing is saved.
const BEAT_MS = 1000;
const COUNT_IN = 3;
const SAYS = 8;
const WORDS = ["بَابْ", "قَلَمْ", "شَمْسْ", "حَبْلْ", "كِتَابْ", "فِيلْ"];
const BEATS_PER_WORD = 2;

type Phase = "idle" | "running" | "checking" | "done" | "failed";

interface Row {
  beat: number;
  expected: number;
  heard: number | null;
}

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

/** For each beat, the first «ب» heard within half a beat of it (not the vowel tail of the beat before). */
function matchBeats(sounds: { phoneme: string; ms: number }[]): Row[] {
  return Array.from({ length: SAYS }, (_, k) => {
    const expected = (COUNT_IN + k) * BEAT_MS;
    const hit = sounds.find(
      (s) =>
        s.phoneme === "b" &&
        s.ms >= expected - BEAT_MS / 2 &&
        s.ms < expected + BEAT_MS / 2,
    );
    return { beat: k + 1, expected, heard: hit?.ms ?? null };
  });
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

export default function MicTest() {
  const recorder = useRecorder();
  const [phase, setPhase] = useState<Phase>("idle");
  const [beat, setBeat] = useState(-1);
  const [mode, setMode] = useState<"ba" | "words">("ba");
  const [test, setTest] = useState<api.TimingTest | null>(null);
  const [error, setError] = useState("");
  const [sound, setSound] = useState(true); // off: follow the pulse on screen only
  const [outputMs, setOutputMs] = useState<number | null>(null);
  const startedAt = useRef(0);
  const audioCtx = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (phase !== "running") return;
    let last = -1;
    const timer = setInterval(() => {
      const b = Math.floor((performance.now() - startedAt.current) / BEAT_MS);
      if (b === last) return;
      last = b;
      if (
        b >=
        COUNT_IN + (mode === "ba" ? SAYS : WORDS.length * BEATS_PER_WORD)
      ) {
        clearInterval(timer);
        void finish();
        return;
      }
      setBeat(b);
      if (sound && audioCtx.current) tick(audioCtx.current, b >= COUNT_IN);
    }, 20);
    return () => clearInterval(timer);
  }, [phase, sound, mode]);

  async function start() {
    setError("");
    if (!(await recorder.start())) return;
    if (sound) {
      audioCtx.current ??= new AudioContext();
      void audioCtx.current.resume();
    }
    startedAt.current = performance.now(); // same order as the game: recording first, then the clock
    setBeat(-1);
    setPhase("running");
  }

  async function finish() {
    const audio = await recorder.stop();
    const ctx = audioCtx.current;
    // How long the browser says a tick takes to reach the speakers; Bluetooth headphones can add 100–300 ms.
    setOutputMs(
      sound && ctx
        ? Math.round((ctx.baseLatency + (ctx.outputLatency ?? 0)) * 1000)
        : null,
    );
    if (!audio) return setPhase("idle");
    setPhase("checking");
    try {
      const run = {
        targets: WORDS,
        slotMs: BEAT_MS * BEATS_PER_WORD,
        firstWordMs: COUNT_IN * BEAT_MS,
      };
      setTest(await api.timingTest(audio, mode === "words" ? run : undefined));
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "فشل الفحص");
      setPhase("failed");
    }
  }

  const sounds = test?.sounds ?? [];
  const rows = matchBeats(sounds);
  const offsets = rows.flatMap((r) =>
    r.heard === null ? [] : [r.heard - r.expected],
  );
  const avg = offsets.length ? mean(offsets) : null;
  const spread = offsets.length
    ? Math.sqrt(mean(offsets.map((o) => (o - avg!) ** 2)))
    : null;

  return (
    <>
      <h1>فحص توقيت الميكروفون</h1>
      <p className="lead">
        ليس لعبة. اضغط «ابدأ»، استمع إلى {COUNT_IN} نبضات، ثم{" "}
        {mode === "ba"
          ? `قل «با» مع كل نبضة (${SAYS} مرات).`
          : `اقرأ كل كلمة بصوت عالٍ عند ظهورها (${WORDS.length} كلمات).`}{" "}
        يُفضَّل استخدام سماعات.
      </p>

      {phase === "running" && (
        <div className="stage">
          <span
            key={beat}
            className={beat >= 0 ? "pulse beat" : "pulse"}
            aria-hidden="true"
          />
          <p className="word">
            {beat < COUNT_IN
              ? beat >= 0
                ? COUNT_IN - beat
                : ""
              : mode === "ba"
                ? "با"
                : (beat - COUNT_IN) % BEATS_PER_WORD === 0
                  ? WORDS[(beat - COUNT_IN) / BEATS_PER_WORD]
                  : " "}
          </p>
        </div>
      )}
      {phase === "checking" && <p className="center-note">جارٍ الفحص…</p>}
      {(error || recorder.error) && (
        <p className="error" role="alert">
          {error || recorder.error}
        </p>
      )}

      {phase === "done" && test?.words && (
        <>
          <p className="level">
            {test.words.filter((w) => w.correct).length} من {WORDS.length} صحيحة
            · {test.words.filter((w) => w.on_time).length} في الوقت
            {test.steadiness_ms != null &&
              ` · التذبذب ${test.steadiness_ms} ms`}
          </p>
          <p>سمع النموذج: «{test.heard_text || "لا شيء"}»</p>
          <div className="card">
            {test.words.map((w, i) => (
              <div
                key={i}
                className={
                  w.correct ? "rhythm-row correct" : "rhythm-row wrong"
                }
              >
                <span className="rhythm-word">{w.target}</span>
                <span>سُمعت: {w.heard_text || "—"}</span>
                <span>{w.correct ? "✓" : FEEDBACK[w.error_type]}</span>
                <span className="rhythm-time" dir="ltr">
                  {w.offset_ms === null
                    ? "—"
                    : `${w.offset_ms >= 0 ? "+" : ""}${w.offset_ms} ms`}
                </span>
              </div>
            ))}
          </div>
          <p>
            الوقت يُقاس من لحظة ظهور الكلمة إلى أول صوت منها، ويشمل وقت قراءتها.
          </p>
        </>
      )}

      {phase === "done" && !test?.words && (
        <>
          <p className="level">
            سُمع {offsets.length} من {SAYS}
            {avg !== null &&
              ` · متوسط الفرق ${Math.round(avg)} ms · التذبذب ${Math.round(spread!)} ms`}
            {outputMs !== null && ` · تأخر خروج الصوت ${outputMs} ms`}
          </p>
          <p>
            من يتبع الإيقاع يسبق النبضة قليلًا عادةً (يتوقّعها)، فالفرق السالب
            الصغير طبيعي وليس خطأً في القياس. أما «التذبذب» فلا يتأثر بالتوقّع ولا
            بتأخر الصوت، ولهذا تقيس اللعبة ثبات الإيقاع به. جرّب مرة مع صوت
            الإيقاع ومرة بدونه (تتبع النبضة على الشاشة) وقارن المتوسط.
          </p>
          <p>
            الفرق الموجب يعني أن الصوت جاء بعد النبضة. في اللعبة تُحسب الكلمة «في
            الوقت» إذا بدأت بين 0 ومدة ظهورها، لذا يجب أن يكون المتوسط موجبًا
            وأقل بكثير من مدة الكلمة (1600–3000 ms)، والتذبذب صغيرًا.
          </p>
          <div className="card" dir="ltr">
            {rows.map((r) => (
              <div key={r.beat} className="rhythm-row">
                <span>beat {r.beat}</span>
                <span>expected {r.expected} ms</span>
                <span>
                  {r.heard === null
                    ? "not heard"
                    : `heard ${r.heard} ms (${r.heard - r.expected >= 0 ? "+" : ""}${r.heard - r.expected})`}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {phase === "done" && (
        <details>
          <summary>كل الأصوات المسموعة ({sounds.length})</summary>
          <pre dir="ltr">
            {sounds.map((s) => `${s.ms}\t${s.phoneme}`).join("\n")}
          </pre>
        </details>
      )}

      {phase !== "running" && phase !== "checking" && (
        <div className="row">
          <label className="check">
            <input
              type="radio"
              checked={mode === "ba"}
              onChange={() => setMode("ba")}
            />
            «با» على الإيقاع
          </label>
          <label className="check">
            <input
              type="radio"
              checked={mode === "words"}
              onChange={() => setMode("words")}
            />
            كلمات حقيقية
          </label>
        </div>
      )}
      {phase !== "running" && phase !== "checking" && (
        <label className="check">
          <input
            type="checkbox"
            checked={sound}
            onChange={(e) => setSound(e.target.checked)}
          />
          صوت الإيقاع
        </label>
      )}
      <div className="row spaced">
        {phase !== "running" && phase !== "checking" && (
          <button className="primary" onClick={() => void start()} autoFocus>
            {phase === "idle" ? "ابدأ" : "أعد الفحص"}
          </button>
        )}
        <Link to="/">رجوع</Link>
      </div>
    </>
  );
}

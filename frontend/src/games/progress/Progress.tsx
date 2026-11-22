import { useEffect, useState } from "react";
import * as api from "../../api";
import { ERROR_NAMES } from "../../shell/feedback";
import { BackLink } from "../../shell/round";
import { usePlayer } from "../../shell/session";

const GAMES = [
  { id: "", name: "كل الألعاب" },
  { id: "word_flash", name: "الكلمة الخاطفة" },
  { id: "sound_surgery", name: "جراحة الأصوات" },
  { id: "rhythmic_reading", name: "القراءة على الإيقاع" },
  { id: "story_recall", name: "قصتي" },
];

const percent = (x: number) => `${Math.round(x * 100)}٪`;
const seconds = (ms: number | null) => (ms === null ? "—" : `${(ms / 1000).toFixed(1)} ث`);

function Bar({ value, label, kind }: { value: number; label: string; kind: "word" | "sound" }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <span className={`bar ${kind}`} role="img" aria-label={`${label}: ${percent(value)}`}>
        <span style={{ width: `${value * 100}%` }} />
      </span>
      <span className="bar-value">{percent(value)}</span>
    </div>
  );
}

export default function Progress() {
  const player = usePlayer();
  const [game, setGame] = useState("");
  const [sessions, setSessions] = useState<api.ProgressSession[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let current = true;
    setSessions(null);
    setError(false);
    api.progress(player.player_id, game || undefined).then(
      (p) => current && setSessions(p.sessions),
      () => current && setError(true),
    );
    return () => {
      current = false;
    };
  }, [player.player_id, game]);

  const latest = sessions?.[sessions.length - 1];
  const errors = Object.entries(
    (sessions ?? []).reduce<Record<string, number>>((sum, s) => {
      for (const [type, n] of Object.entries(s.errors)) sum[type] = (sum[type] ?? 0) + (n ?? 0);
      return sum;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);
  const mostErrors = errors[0]?.[1] ?? 1;

  return (
    <>
      <h1>تقدّمي</h1>
      <label className="inline">
        اللعبة
        <select value={game} onChange={(e) => setGame(e.target.value)}>
          {GAMES.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </label>

      {error && (
        <p className="error" role="alert">
          تعذّر تحميل التقدّم.
        </p>
      )}
      {!error && !sessions && <p className="center-note">جارٍ التحميل…</p>}
      {sessions?.length === 0 && <p className="lead">لا توجد محاولات بعد. العب جولة ثم عُد إلى هنا.</p>}

      {latest && (
        <>
          <h2>آخر يوم ({latest.date})</h2>
          <div className="stats">
            <div className="stat">
              <span className="stat-value">{percent(latest.accuracy)}</span>
              <span>كلمات صحيحة</span>
            </div>
            <div className="stat">
              <span className="stat-value">{percent(latest.phoneme_accuracy)}</span>
              <span>أصوات صحيحة</span>
            </div>
            <div className="stat">
              <span className="stat-value">{seconds(latest.avg_response_ms)}</span>
              <span>متوسط وقت الإجابة</span>
            </div>
          </div>

          <h2>كل يوم</h2>
          {sessions.map((s) => (
            <div key={s.date} className="day">
              <p className="day-title">
                {s.date} · {seconds(s.avg_response_ms)}
              </p>
              <Bar value={s.accuracy} label="الكلمات" kind="word" />
              <Bar value={s.phoneme_accuracy} label="الأصوات" kind="sound" />
            </div>
          ))}

          {errors.length > 0 && (
            <>
              <h2>أكثر ما نتدرّب عليه</h2>
              {errors.map(([type, n]) => (
                <div key={type} className="bar-row">
                  <span className="bar-label">{ERROR_NAMES[type as api.ErrorType] ?? type}</span>
                  <span className="bar errors" role="img" aria-label={`${n}`}>
                    <span style={{ width: `${(n / mostErrors) * 100}%` }} />
                  </span>
                  <span className="bar-value">{n}</span>
                </div>
              ))}
            </>
          )}
        </>
      )}
      <div className="row spaced">
        <BackLink />
      </div>
    </>
  );
}

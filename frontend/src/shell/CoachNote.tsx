import { useEffect, useState } from "react";
import * as api from "../api";
import { usePlayer } from "./session";

/** The coach's note. Shows nothing until it arrives, and nothing at all if the coach is unavailable:
 *  the fixed feedback is already on screen. */
export default function CoachNote({ kind, attempts }: { kind: "word" | "round"; attempts: api.Attempt[] }) {
  const player = usePlayer();
  const [text, setText] = useState<string | null>(null);
  const key = JSON.stringify(attempts);

  useEffect(() => {
    let live = true;
    setText(null);
    api.coach(player.player_id, kind, JSON.parse(key)).then(
      (r) => live && setText(r.text),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [player.player_id, kind, key]);

  if (!text) return null;
  return (
    <div className="coach" role="status">
      <span className="coach-label">ملاحظة المدرّب</span>
      <p>{text}</p>
    </div>
  );
}

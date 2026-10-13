// The single API client. Every call to the backend goes through here (HANDOFF.md section 10).
// Shapes mirror backend/app/schemas.py, which is the frozen contract in HANDOFF.md section 4.

export type ErrorType =
  | "none"
  | "letter_reversal"
  | "missing_sound"
  | "added_sound"
  | "substitution"
  | "no_response";

export interface ScoreResult {
  heard: string;
  target_phonemes: string[];
  heard_phonemes: string[];
  correct: boolean;
  phoneme_accuracy: number;
  response_ms: number | null;
  error_type: ErrorType;
}

export interface Exercise {
  game: string;
  level: number;
  items: string[];
  display_ms: number;
  reason: string;
}

export interface Question {
  q: string;
  answer: string;
}

export interface Story {
  story: string;
  questions: Question[];
}

export interface ProgressSession {
  date: string;
  accuracy: number;
  phoneme_accuracy: number;
  avg_response_ms: number | null;
  errors: Partial<Record<ErrorType, number>>;
}

export interface Progress {
  sessions: ProgressSession[];
}

export interface Player {
  player_id: string;
  name: string;
  interests: string[];
}

export interface LoginResult extends Player {
  token: string;
}

/** status 0 means the server could not be reached at all. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

/** The login token is sent as "Authorization: Bearer <token>" on every request. */
export function setToken(value: string | null): void {
  token = value;
}

/** Called when the server rejects the current token (login expired), so the shell can show the login screen. */
export function setOnUnauthorized(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

// FastAPI errors are {"detail": "..."}; validation errors (422) carry a list of {msg, loc}.
async function errorDetail(res: Response): Promise<string> {
  try {
    const { detail } = await res.json();
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(". ");
  } catch {
    // not JSON: fall through
  }
  return `Request failed (${res.status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!BASE_URL) throw new ApiError(0, "VITE_API_BASE_URL is not set");
  const sentToken = token;
  const headers = new Headers(init.headers);
  if (sentToken) headers.set("Authorization", `Bearer ${sentToken}`);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server");
  }
  if (!res.ok) {
    if (res.status === 401 && sentToken) onUnauthorized?.();
    throw new ApiError(res.status, await errorDetail(res));
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function health(): Promise<{ ok: boolean; mock: boolean }> {
  return request("/health");
}

export function register(name: string, password: string, interests: string[]): Promise<LoginResult> {
  return postJson("/players", { name, password, interests });
}

export function login(name: string, password: string): Promise<LoginResult> {
  return postJson("/login", { name, password });
}

export function startGuest(interests: string[] = []): Promise<LoginResult> {
  return postJson("/guest", { interests });
}

export function me(): Promise<Player> {
  return request("/me");
}

export function logout(): Promise<void> {
  return request("/logout", { method: "POST" });
}

export interface Answer {
  /** What the player should say. */
  target: string;
  game: string;
  /** Date.now() when the prompt appeared. */
  shownAtMs?: number;
  /** Mic answer. */
  audio?: Blob;
  /** Debug answer: scored instead of audio. Leave both out when the player said nothing. */
  heardText?: string;
}

export function score(answer: Answer): Promise<ScoreResult> {
  const form = new FormData();
  form.append("target", answer.target);
  form.append("game", answer.game);
  if (answer.shownAtMs !== undefined) form.append("shown_at_ms", String(answer.shownAtMs));
  if (answer.audio) {
    // Safari records mp4, Chrome and Firefox record webm: the backend accepts both.
    const ext = answer.audio.type.includes("mp4") ? "mp4" : "webm";
    form.append("audio", answer.audio, `answer.${ext}`);
  } else if (answer.heardText) {
    form.append("heard_text", answer.heardText);
  }
  return request("/score", { method: "POST", body: form });
}

/** history = the /score results of the round just played (empty on the first call). */
export function nextExercise(playerId: string, game: string, history: ScoreResult[]): Promise<Exercise> {
  return postJson("/next-exercise", { player_id: playerId, game, history });
}

/** Empty weak_sounds and interests are filled in by the server from the player's attempts and profile. */
export function story(playerId: string, weakSounds: string[] = [], interests: string[] = []): Promise<Story> {
  return postJson("/story", { player_id: playerId, weak_sounds: weakSounds, interests });
}

export function progress(playerId: string, game?: string): Promise<Progress> {
  const query = game ? `?game=${encodeURIComponent(game)}` : "";
  return request(`/progress/${encodeURIComponent(playerId)}${query}`);
}

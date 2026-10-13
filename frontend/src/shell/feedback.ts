import type { ErrorType } from "../api";

// Placeholder wording until content/feedback.json arrives (Content, Day 1). Keep it kind, and never medical.
export const FEEDBACK: Record<ErrorType, string> = {
  none: "Spot on!",
  letter_reversal: "Two letters that look alike got swapped, like b and d. They are tricky!",
  missing_sound: "One sound went missing. Try to say every sound.",
  added_sound: "An extra sound slipped in.",
  substitution: "One sound came out different.",
  no_response: "No answer that time. That is okay.",
};

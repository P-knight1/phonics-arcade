import type { ErrorType } from "../api";

// Placeholder wording until content/feedback.json arrives (Content, Day 1). Keep it kind, and never medical.
export const FEEDBACK: Record<ErrorType, string> = {
  none: "Spot on!",
  letter_reversal: "Two letters that look alike got swapped, like b and d. They are tricky!",
  missing_sound: "One sound went missing. Try to say every sound.",
  added_sound: "An extra sound slipped in.",
  substitution: "One sound came out different.",
  no_response: "No answer that time. That is okay.",
  dot_confusion: "Two letters that differ only by their dots got mixed up. Look closely at the dots!",
  vowel_error: "One short vowel mark (haraka) was read differently.",
  vowel_length: "A vowel was read too long or too short.",
  letter_position: "Two letters swapped places.",
};

import type { ErrorType } from "../api";

// Shown after a wrong answer. Kind, specific, never clinical.
export const FEEDBACK: Record<ErrorType, string> = {
  none: "أحسنت!",
  letter_reversal: "تبادل حرفان متشابهان مكانيهما. هذا يحدث كثيرًا!",
  missing_sound: "سقط صوت من الكلمة. حاول أن تنطق كل الأصوات.",
  added_sound: "دخل صوت زائد على الكلمة.",
  substitution: "خرج أحد الأصوات مختلفًا.",
  no_response: "لم تُجب هذه المرة، ولا بأس.",
  dot_confusion: "اختلط حرفان لا يفرّق بينهما إلا النقاط. انظر إلى النقاط جيدًا!",
  vowel_error: "قُرئت إحدى الحركات بشكل مختلف. انتبه إلى الفتحة والضمة والكسرة.",
  vowel_length: "مُدّ صوت قصير أو قُصِّر صوت طويل.",
  letter_position: "تبادل حرفان مكانيهما في الكلمة.",
};

// Short names for the progress screen.
export const ERROR_NAMES: Record<ErrorType, string> = {
  none: "صحيح",
  letter_reversal: "حرفان متبادلان",
  missing_sound: "صوت ناقص",
  added_sound: "صوت زائد",
  substitution: "صوت مختلف",
  no_response: "بلا إجابة",
  dot_confusion: "النقاط",
  vowel_error: "الحركات",
  vowel_length: "المدّ",
  letter_position: "ترتيب الحروف",
};

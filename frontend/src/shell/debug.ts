// Debug mode (HANDOFF.md section 5): "?debug=1" shows the placeholder answer buttons under the mic.
// It is remembered for the tab, so it survives moving between pages. "?debug=0" turns it off.
const KEY = "phonics-arcade.debug";

function read(): boolean {
  try {
    const param = new URLSearchParams(window.location.search).get("debug");
    if (param !== null) sessionStorage.setItem(KEY, param === "1" ? "1" : "0");
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export const DEBUG = read();

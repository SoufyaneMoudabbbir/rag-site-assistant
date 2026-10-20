// Styles live inside the widget's Shadow DOM, so the host site's CSS
// cannot change them and they cannot leak into the host site.
export const css = `
:host { all: initial; }
* { box-sizing: border-box; }
.root {
  --c: #b5562b;
  --bg: #ffffff;
  --bg2: #f5f4f1;
  --text: #1f1d1b;
  --muted: #6c6862;
  --line: #e7e4df;
  font: 14.5px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--text);
}
/* Light by default so the widget matches typical client sites; data-theme="dark" or "auto" opts in. */
.root.dark { --bg: #1d1c1b; --bg2: #2a2927; --text: #f0eee9; --muted: #a8a49d; --line: #393733; }
@media (prefers-color-scheme: dark) {
  .root.auto { --bg: #1d1c1b; --bg2: #2a2927; --text: #f0eee9; --muted: #a8a49d; --line: #393733; }
}
button { font: inherit; cursor: pointer; }

.launcher {
  position: fixed; right: 20px; bottom: 20px; z-index: 2147483646;
  width: 58px; height: 58px; border-radius: 50%; border: none;
  background: var(--c); color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px rgba(0,0,0,.22);
  transition: transform .15s ease;
}
.launcher:hover { transform: scale(1.06); }
.launcher svg { width: 26px; height: 26px; }
.launcher.loading svg { animation: breathe 1s ease-in-out infinite; }
@keyframes breathe { 50% { opacity: .35; transform: scale(.85); } }

.teaser {
  position: fixed; right: 20px; bottom: 90px; z-index: 2147483646;
  max-width: 250px; padding: 11px 32px 11px 14px;
  background: var(--bg); color: var(--text); border: 1px solid var(--line);
  border-radius: 14px 14px 4px 14px; box-shadow: 0 6px 20px rgba(0,0,0,.14);
  animation: pop .25s ease;
}
.teaser button.x { position: absolute; top: 6px; right: 6px; border: none; background: none; color: var(--muted); font-size: 16px; line-height: 1; padding: 2px 5px; }
.teaser .open { all: unset; cursor: pointer; }

.panel {
  position: fixed; right: 20px; bottom: 90px; z-index: 2147483647;
  width: 380px; height: min(620px, calc(100vh - 110px));
  display: flex; flex-direction: column;
  background: var(--bg); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0,0,0,.25); overflow: hidden;
  animation: pop .2s ease;
}
@keyframes pop { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

.head { display: flex; align-items: center; gap: 10px; padding: 12px 12px 12px 14px; background: var(--c); color: #fff; }
.avatar { width: 34px; height: 34px; border-radius: 50%; background: rgba(255,255,255,.22); display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
.head .title { font-weight: 650; line-height: 1.2; }
.head .sub { font-size: 12px; opacity: .85; display: flex; align-items: center; gap: 5px; }
.head .dot { width: 7px; height: 7px; border-radius: 50%; background: #7ee2a0; }
.head .close { margin-left: auto; border: none; background: rgba(255,255,255,.15); color: #fff; border-radius: 8px; width: 32px; height: 32px; font-size: 18px; }
.head .close:hover { background: rgba(255,255,255,.28); }

.msgs { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; background: var(--bg); }
.msgs > * { flex-shrink: 0; } /* a full chat scrolls; it never squeezes cards or bubbles */
.msg { max-width: 86%; padding: 9px 12px; border-radius: 14px; white-space: normal; overflow-wrap: anywhere; }
.msg.bot { background: var(--bg2); border-bottom-left-radius: 4px; align-self: flex-start; }
.msg.user { background: var(--c); color: #fff; border-bottom-right-radius: 4px; align-self: flex-end; }
.msg p { margin: 0 0 6px; } .msg p:last-child { margin: 0; }
.msg ul { margin: 4px 0; padding-left: 18px; }
.msg a { color: inherit; }
.msg.error { background: #fdecea; color: #8a1c12; }
.sources { display: flex; flex-wrap: wrap; gap: 6px; margin-top: -4px; align-self: flex-start; max-width: 86%; }
.sources a { font-size: 12px; text-decoration: none; color: var(--c); border: 1px solid var(--line); background: var(--bg); padding: 3px 9px; border-radius: 999px; }
.sources a:hover { border-color: var(--c); }
.cards { display: flex; gap: 8px; overflow-x: auto; align-self: stretch; margin-top: -2px; padding: 2px 2px 4px; scroll-snap-type: x mandatory; }
.card { flex: 0 0 148px; scroll-snap-align: start; display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--bg); color: var(--text); text-decoration: none; transition: border-color .15s, transform .15s; }
.card:hover { border-color: var(--c); transform: translateY(-1px); }
.card img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; background: var(--bg2); }
.card .info { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px 10px; }
.card .name { font-weight: 600; font-size: 13px; line-height: 1.3; }
.card .price { color: var(--c); font-weight: 700; font-size: 13px; }
.card .cta { font-size: 12px; color: var(--muted); margin-top: 2px; }
.typing { display: inline-flex; gap: 4px; padding: 12px 14px; }
.typing span { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); animation: blink 1.2s infinite; }
.typing span:nth-child(2) { animation-delay: .2s; } .typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }

.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 14px 10px; }
.chips button { border: 1px solid var(--line); background: var(--bg); color: var(--text); border-radius: 999px; padding: 6px 11px; font-size: 13px; }
.chips button:hover { border-color: var(--c); color: var(--c); }

.handoff { align-self: stretch; border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: var(--bg); display: flex; flex-direction: column; gap: 8px; }
.handoff strong { font-size: 13.5px; }
.handoff input, .handoff textarea { width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font: inherit; background: var(--bg); color: var(--text); }
.handoff textarea { resize: vertical; min-height: 60px; }
.handoff .row { display: flex; gap: 8px; justify-content: flex-end; }
.btn { border: none; border-radius: 8px; padding: 8px 14px; background: var(--c); color: #fff; font-weight: 600; }
.btn.ghost { background: transparent; color: var(--muted); }
.btn:disabled { opacity: .6; cursor: default; }
.note { font-size: 12.5px; color: var(--muted); }

form.ask { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--line); background: var(--bg); }
form.ask textarea { flex: 1; resize: none; border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px; font: inherit; max-height: 110px; background: var(--bg); color: var(--text); }
form.ask textarea:focus, .handoff input:focus, .handoff textarea:focus { outline: 2px solid var(--c); outline-offset: -1px; border-color: transparent; }
form.ask button { width: 42px; border-radius: 12px; border: none; background: var(--c); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
form.ask button:disabled { opacity: .5; cursor: default; }
.foot { display: flex; justify-content: space-between; gap: 8px; padding: 0 12px 9px; font-size: 11.5px; color: var(--muted); background: var(--bg); }
.foot button { border: none; background: none; color: var(--muted); text-decoration: underline; padding: 0; font-size: 11.5px; }

@media (max-width: 480px) {
  .panel { right: 0; bottom: 0; width: 100vw; height: 100dvh; border-radius: 0; border: none; }
  .teaser { right: 16px; }
}
`;

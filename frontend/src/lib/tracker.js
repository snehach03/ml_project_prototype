/**
 * BehaviorTracker - collects ONLY aggregated interaction counters.
 *
 * PRIVACY GUARANTEES (enforced by code and by src/test/tracker.test.js):
 *   - The value of a pressed key is classified on the spot (printable / space /
 *     backspace / arrow / ...) and then thrown away. Key identities, typed text,
 *     input values, URLs and page content are never stored or sent.
 *   - Keystrokes inside password fields, or any element marked data-private,
 *     are ignored completely (not even their timing is kept).
 *   - Every minute the tracker emits one object of numbers. Nothing else leaves.
 *   - Listeners exist only between start() and stop().
 *
 * The field names are the same ones the backend/model use (ml/config.py).
 * Browser events only approximate the uLog counters the model was trained on:
 *   mouse_act      = bursts of mouse movement separated by >250 ms of stillness
 *   wheel          = bursts of wheel events separated by >150 ms
 *   app_changes    = window blur events (page loses focus)
 *   tab_changes    = page-visibility changes to "hidden"
 * and only events on THIS page are visible (uLog logged the whole computer).
 */

const MODIFIER_KEYS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "AltGraph", "Fn", "OS"]);
const MOUSE_BURST_GAP_MS = 250;
const WHEEL_BURST_GAP_MS = 150;
const IDLE_AFTER_MS = 3000;
const IKI_PAUSE_MS = 5000;     // longer gaps are pauses, not typing rhythm
const DRAG_MIN_PIXELS = 5;

export const MINUTE_SECONDS = 60;

function emptyCounters() {
  return {
    mouse_act: 0, left_clicks: 0, right_clicks: 0, double_clicks: 0, wheel: 0, drags: 0,
    mouse_distance: 0, keystrokes: 0, chars: 0, special_keys: 0, direction_keys: 0,
    error_keys: 0, shortcut_keys: 0, spaces: 0, app_changes: 0, tab_changes: 0,
  };
}

function isPrivateTarget(target) {
  if (!target || !target.closest) return false;
  if (target.tagName === "INPUT" && target.type === "password") return true;
  return target.closest("[data-private]") !== null;
}

function meanOf(values) {
  if (values.length === 0) return null;
  let total = 0;
  for (let i = 0; i < values.length; i += 1) total += values[i];
  return total / values.length;
}

function stdOf(values) {
  if (values.length < 2) return null;
  const mean = meanOf(values);
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) sum += (values[i] - mean) * (values[i] - mean);
  return Math.sqrt(sum / (values.length - 1));
}

export class BehaviorTracker {
  constructor(onMinute, options = {}) {
    this.onMinute = onMinute;
    this.target = options.target || document;
    this.win = options.win || window;
    this.now = options.now || (() => Date.now());
    this.running = false;
    this.handlers = [];
    this.resetMinute();
  }

  resetMinute() {
    this.counters = emptyCounters();
    this.intervals = [];            // inter-key intervals in ms (numbers only)
    this.idleSeconds = 0;
    this.secondsInMinute = 0;
    this.lastActivity = this.now();
    this.lastKeyTime = null;
  }

  // ---- lifecycle ------------------------------------------------------
  start() {
    if (this.running) return;
    this.running = true;
    this.resetMinute();
    this.lastMouse = null;
    this.lastMouseMoveTime = 0;
    this.lastWheelTime = 0;
    this.mouseDown = false;
    this.dragDistance = 0;

    this.listen(this.target, "keydown", (e) => this.onKeyDown(e), true);
    this.listen(this.target, "mousemove", (e) => this.onMouseMove(e));
    this.listen(this.target, "mousedown", (e) => this.onMouseDown(e));
    this.listen(this.target, "mouseup", () => this.onMouseUp());
    this.listen(this.target, "click", (e) => this.onClick(e));
    this.listen(this.target, "dblclick", () => this.bump("double_clicks"));
    this.listen(this.target, "contextmenu", () => this.bump("right_clicks"));
    this.listen(this.target, "wheel", () => this.onWheel(), false, { passive: true });
    this.listen(this.target, "visibilitychange", () => this.onVisibility());
    this.listen(this.win, "blur", () => this.bump("app_changes", false));

    this.timer = setInterval(() => this.tick(), 1000);
  }

  stop() {
    if (!this.running) return;
    this.running = false;
    clearInterval(this.timer);
    for (let i = 0; i < this.handlers.length; i += 1) {
      const h = this.handlers[i];
      h.target.removeEventListener(h.type, h.fn, h.capture);
    }
    this.handlers = [];
    // a partial minute is discarded on purpose: the model was trained on full minutes
    this.resetMinute();
  }

  listen(target, type, fn, capture = false, extra = undefined) {
    target.addEventListener(type, fn, extra !== undefined ? { capture, ...extra } : capture);
    this.handlers.push({ target, type, fn, capture });
  }

  // ---- event handlers (counters only) -----------------------------------
  markActivity() {
    this.lastActivity = this.now();
  }

  bump(name, isActivity = true) {
    this.counters[name] += 1;
    if (isActivity) this.markActivity();
  }

  onKeyDown(event) {
    if (event.repeat) return;
    if (MODIFIER_KEYS.has(event.key)) return;
    if (isPrivateTarget(event.target)) return;      // password fields: ignore completely

    // classify, count, forget. event.key is never stored anywhere.
    const key = event.key;
    this.counters.keystrokes += 1;
    if (event.ctrlKey || event.metaKey) {
      this.counters.shortcut_keys += 1;
    } else if (key === "Backspace" || key === "Delete") {
      this.counters.error_keys += 1;
      this.counters.special_keys += 1;
    } else if (key.startsWith("Arrow")) {
      this.counters.direction_keys += 1;
    } else if (key === " ") {
      this.counters.spaces += 1;
      this.counters.chars += 1;
    } else if (key.length === 1) {
      this.counters.chars += 1;
    } else {
      this.counters.special_keys += 1;
    }

    const time = this.now();
    if (this.lastKeyTime !== null) {
      const gap = time - this.lastKeyTime;
      if (gap > 0 && gap < IKI_PAUSE_MS) this.intervals.push(gap);
    }
    this.lastKeyTime = time;
    this.markActivity();
  }

  onMouseMove(event) {
    const time = this.now();
    if (time - this.lastMouseMoveTime > MOUSE_BURST_GAP_MS) this.counters.mouse_act += 1;
    this.lastMouseMoveTime = time;

    if (this.lastMouse !== null) {
      const dx = event.clientX - this.lastMouse.x;
      const dy = event.clientY - this.lastMouse.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      this.counters.mouse_distance += distance;
      if (this.mouseDown) this.dragDistance += distance;
    }
    this.lastMouse = { x: event.clientX, y: event.clientY };
    this.markActivity();
  }

  onMouseDown() {
    this.mouseDown = true;
    this.dragDistance = 0;
  }

  onMouseUp() {
    if (this.mouseDown && this.dragDistance >= DRAG_MIN_PIXELS) this.counters.drags += 1;
    this.mouseDown = false;
    this.dragDistance = 0;
  }

  onClick(event) {
    if (event.button === 0) this.bump("left_clicks");
  }

  onWheel() {
    const time = this.now();
    if (time - this.lastWheelTime > WHEEL_BURST_GAP_MS) this.counters.wheel += 1;
    this.lastWheelTime = time;
    this.markActivity();
  }

  onVisibility() {
    if (this.target.visibilityState === "hidden") this.bump("tab_changes", false);
  }

  // ---- per-second tick / per-minute flush ---------------------------------
  tick() {
    this.secondsInMinute += 1;
    if (this.now() - this.lastActivity >= IDLE_AFTER_MS) this.idleSeconds += 1;
    if (this.secondsInMinute >= MINUTE_SECONDS) this.flushMinute();
  }

  buildMinute() {
    const minute = {};
    const names = Object.keys(this.counters);
    for (let i = 0; i < names.length; i += 1) {
      minute[names[i]] = Math.round(this.counters[names[i]] * 100) / 100;
    }
    const mean = meanOf(this.intervals);
    const std = stdOf(this.intervals);
    if (mean !== null) minute.iki_mean_ms = Math.round(mean);
    if (std !== null) minute.iki_std_ms = Math.round(std);
    minute.idle_seconds = Math.min(60, this.idleSeconds);
    return minute;
  }

  flushMinute() {
    const minute = this.buildMinute();
    this.resetMinute();
    try {
      this.onMinute(minute);
    } catch (error) {
      console.error("minute callback failed", error);
    }
  }

  /** Live preview of the minute in progress (numbers only), for the UI. */
  snapshot() {
    return { ...this.counters, seconds: this.secondsInMinute, idle_seconds: this.idleSeconds };
  }
}

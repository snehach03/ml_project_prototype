import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { BehaviorTracker } from "../lib/tracker.js";

function key(type, init) {
  return new KeyboardEvent(type, { bubbles: true, cancelable: true, ...init });
}

describe("BehaviorTracker", () => {
  let tracker;
  let minutes;
  let clock;

  beforeEach(() => {
    vi.useFakeTimers();
    clock = 1_000_000;
    minutes = [];
    tracker = new BehaviorTracker((m) => minutes.push(m), { now: () => clock });
    tracker.start();
  });

  afterEach(() => {
    tracker.stop();
    vi.useRealTimers();
  });

  function advance(ms) {
    clock += ms;
    vi.advanceTimersByTime(ms);
  }

  it("classifies keys into counters and never stores the key itself", () => {
    const text = "hunter2 secret";
    for (const ch of text) {
      document.dispatchEvent(key("keydown", { key: ch }));
      advance(120);
    }
    document.dispatchEvent(key("keydown", { key: "Backspace" }));
    document.dispatchEvent(key("keydown", { key: "ArrowLeft" }));
    document.dispatchEvent(key("keydown", { key: "c", ctrlKey: true }));
    document.dispatchEvent(key("keydown", { key: "Shift" }));     // modifier alone: ignored

    const snap = tracker.snapshot();
    expect(snap.keystrokes).toBe(text.length + 3);
    expect(snap.chars).toBe(text.length);
    expect(snap.spaces).toBe(1);
    expect(snap.error_keys).toBe(1);
    expect(snap.direction_keys).toBe(1);
    expect(snap.shortcut_keys).toBe(1);

    advance(60_000);
    expect(minutes.length).toBeGreaterThanOrEqual(1);
    const serialised = JSON.stringify(minutes);
    expect(serialised).not.toContain("hunter");
    expect(serialised).not.toContain("secret");
    for (const value of Object.values(minutes[0])) expect(typeof value).toBe("number");
  });

  it("ignores password fields and data-private elements completely", () => {
    const password = document.createElement("input");
    password.type = "password";
    const secretArea = document.createElement("div");
    secretArea.setAttribute("data-private", "");
    const inner = document.createElement("input");
    secretArea.appendChild(inner);
    document.body.appendChild(password);
    document.body.appendChild(secretArea);

    password.dispatchEvent(key("keydown", { key: "a" }));
    inner.dispatchEvent(key("keydown", { key: "b" }));
    expect(tracker.snapshot().keystrokes).toBe(0);
  });

  it("counts clicks, scroll bursts, mouse distance and visibility changes", () => {
    document.dispatchEvent(new MouseEvent("mousemove", { clientX: 0, clientY: 0 }));
    advance(400);
    document.dispatchEvent(new MouseEvent("mousemove", { clientX: 30, clientY: 40 }));
    document.dispatchEvent(new MouseEvent("click", { button: 0, bubbles: true }));
    document.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true }));
    document.dispatchEvent(new WheelEvent("wheel"));
    advance(50);
    document.dispatchEvent(new WheelEvent("wheel"));       // same burst
    advance(300);
    document.dispatchEvent(new WheelEvent("wheel"));       // new burst

    const snap = tracker.snapshot();
    expect(snap.mouse_distance).toBeCloseTo(50, 5);
    expect(snap.mouse_act).toBe(2);
    expect(snap.left_clicks).toBe(1);
    expect(snap.right_clicks).toBe(1);
    expect(snap.wheel).toBe(2);
  });

  it("stops listening after stop() and discards the partial minute", () => {
    document.dispatchEvent(key("keydown", { key: "a" }));
    tracker.stop();
    document.dispatchEvent(key("keydown", { key: "b" }));
    expect(tracker.snapshot().keystrokes).toBe(0);
    advance(120_000);
    expect(minutes.length).toBe(0);
  });
});

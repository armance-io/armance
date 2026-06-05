import { describe, expect, it } from "vitest";
import { SSE_EVENT_NAMES } from "../sse";

describe("SSE_EVENT_NAMES", () => {
  // Named SSE events arrive with an `event:` field, so EventSource only
  // delivers them to a matching addEventListener — never to onmessage. Any
  // backend-emitted named event missing here is silently dropped by the browser.
  it("listens for the recruit refresh event", () => {
    expect(SSE_EVENT_NAMES).toContain("agents.proposed");
  });

  it("listens for the core turn + streaming events", () => {
    for (const name of [
      "turn.completed",
      "turn.error",
      "agent.streaming.started",
      "agent.streaming.end",
    ]) {
      expect(SSE_EVENT_NAMES).toContain(name);
    }
  });
});

import { describe, expect, it } from "vitest";
import { displayAgentName } from "../agentNames";

describe("displayAgentName", () => {
  it("maps core staff keys to display names", () => {
    expect(displayAgentName("system-context")).toBe("Armance");
    expect(displayAgentName("system-hr")).toBe("Malik");
    expect(displayAgentName("embedding")).toBe("Library");
  });

  it("attributes persona-writer recruitment calls to Malik", () => {
    expect(displayAgentName("persona-writer")).toBe("Malik");
    // underscore variant normalises to the same key
    expect(displayAgentName("persona_writer")).toBe("Malik");
  });

  it("leaves specialist names untouched", () => {
    expect(displayAgentName("Claire")).toBe("Claire");
  });
});

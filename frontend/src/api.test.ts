import { describe, expect, it } from "vitest";
import { parseTrajectoryText } from "./api";

describe("parseTrajectoryText", () => {
  it("rejects text that is not JSON", () => {
    expect(() => parseTrajectoryText("{")).toThrow("The file is not valid JSON.");
  });

  it("rejects a JSON list", () => {
    expect(() => parseTrajectoryText("[]")).toThrow(
      "Upload one trajectory object. This file is a list of runs.",
    );
  });

  it("rejects a JSON number", () => {
    expect(() => parseTrajectoryText("4")).toThrow("A trajectory must be a JSON object.");
  });

  it("drops expected_findings and keeps the other fields", () => {
    const parsed = parseTrajectoryText(
      JSON.stringify({
        run_id: "demo-1",
        task_id: "cache lookup",
        expected_findings: ["symptom_fix"],
      }),
    );
    expect(parsed).toEqual({
      run_id: "demo-1",
      task_id: "cache lookup",
    });
    expect(Object.hasOwn(parsed, "expected_findings")).toBe(false);
  });
});

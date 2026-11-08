export const FAILURE_TYPES = [
  "command_loop",
  "edit_then_fail",
  "false_success_claim",
  "gave_up_early",
  "symptom_fix",
  "ignored_error",
  "no_test_run",
] as const;

const TYPE_LABELS: Record<string, string> = {
  command_loop: "Command loop",
  edit_then_fail: "Edit then fail",
  false_success_claim: "False success claim",
  gave_up_early: "Gave up early",
  symptom_fix: "Symptom fix",
  ignored_error: "Ignored error",
  no_test_run: "No test run",
};

export const TYPE_COLORS: Record<string, string> = {
  command_loop: "#1d4ed8",
  edit_then_fail: "#b45309",
  false_success_claim: "#be123c",
  gave_up_early: "#6d28d9",
  symptom_fix: "#0f766e",
  ignored_error: "#0369a1",
  no_test_run: "#a16207",
};

export function findingLabel(type: string): string {
  return TYPE_LABELS[type] ?? type.replaceAll("_", " ");
}

export function findingColor(type: string): string {
  return TYPE_COLORS[type] ?? "#57534e";
}

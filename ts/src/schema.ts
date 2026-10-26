import type { ShowChartArgs } from "./index.js";

/** The parts of Standard Schema v1 (https://standardschema.dev) a chat framework reads. */
export interface StandardSchema<Output> {
  readonly "~standard": {
    readonly version: 1;
    readonly vendor: string;
    readonly validate: (
      value: unknown,
    ) =>
      | { readonly value: Output; readonly issues?: undefined }
      | { readonly issues: ReadonlyArray<{ readonly message: string }> };
    readonly types?: { readonly input: unknown; readonly output: Output } | undefined;
  };
}

/**
 * `show_chart`'s arguments as a Standard Schema, for frameworks that type a tool renderer by
 * one. The server checks the arguments; this only says their shape.
 */
export const showChartArgs: StandardSchema<ShowChartArgs> = {
  "~standard": {
    version: 1,
    vendor: "s-layer",
    validate(value) {
      const issues: { message: string }[] = [];
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        return { issues: [{ message: "show_chart takes an object" }] };
      }
      const args = value as Record<string, unknown>;
      for (const key of ["result_id", "chart_type", "title"] as const) {
        if (typeof args[key] !== "string") issues.push({ message: `${key} must be a string` });
      }
      if (typeof args.encodings !== "object" || args.encodings === null) {
        issues.push({ message: "encodings must be an object" });
      }
      return issues.length > 0 ? { issues } : { value: args as unknown as ShowChartArgs };
    },
  },
};

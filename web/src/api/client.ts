// A typed API client: every path, parameter and response shape comes from
// schema.d.ts, which is generated from the Python API (`npm run gen:api`).
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

type Schemas = components["schemas"];
export type Team = Schemas["Team"];
export type Player = Schemas["Player"];
export type GameSummary = Schemas["GameSummary"];
export type GameDetail = Schemas["GameDetail"];
export type Lineup = Schemas["Lineup"];
export type WinProbPoint = Schemas["WinProbPoint"];
export type Killshot = Schemas["Killshot"];
export type Ratings = Schemas["Ratings"];
export type OnOff = Schemas["OnOff"];
export type PlayerAdvanced = Schemas["PlayerAdvanced"];
export type Season = Schemas["Season"];
export type PushSubscriptionBody = Schemas["PushSubscription"];

/** Turn openapi-fetch's {data, error} answer into data, or a thrown error TanStack Query can show. */
export async function unwrap<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await request;
  if (error !== undefined || data === undefined) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return data;
}

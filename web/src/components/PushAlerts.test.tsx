import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { api } from "../api/client";
import { PushAlerts } from "./PushAlerts";

// Mocked here so the test drives push.ts's logic (key encoding, subscribe/unsubscribe
// calls) without needing a real network or openapi-fetch's response parsing.
vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { GET: vi.fn(), POST: vi.fn() } };
});

const mockedGet = api.GET as unknown as Mock;
const mockedPost = api.POST as unknown as Mock;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  mockedGet.mockReset();
  mockedPost.mockReset();
});

/** A fake PushSubscription, just enough for push.ts to read from it. */
function fakeSubscription(endpoint: string) {
  return { endpoint, getKey: () => new Uint8Array([1, 2, 3]).buffer, unsubscribe: vi.fn().mockResolvedValue(undefined) };
}

/** Stubs the browser APIs lib/push.ts needs, and the API calls. */
function stubPushApi({ alreadySubscribed = false } = {}) {
  const subscription = fakeSubscription("https://push.example/abc");
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(alreadySubscribed ? subscription : null),
    subscribe: vi.fn().mockResolvedValue(subscription),
  };
  vi.stubGlobal("navigator", {
    ...navigator,
    serviceWorker: { register: vi.fn().mockResolvedValue({ pushManager }) },
  });
  vi.stubGlobal("PushManager", function () {});
  vi.stubGlobal("Notification", { requestPermission: vi.fn().mockResolvedValue("granted") });
  mockedGet.mockResolvedValue({ data: { public_key: "test-key" }, response: new Response() });
  mockedPost.mockResolvedValue({ data: { ok: true }, response: new Response() });
  return { subscription, pushManager };
}

describe("PushAlerts", () => {
  it("shows nothing when the browser can't do push", () => {
    render(<PushAlerts />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("subscribes on click and then shows alerts are on", async () => {
    const { pushManager } = stubPushApi();
    render(<PushAlerts />);
    await waitFor(() => expect(screen.getByText("Killshot alerts")).toBeTruthy());

    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByText("Alerts on")).toBeTruthy());
    expect(pushManager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true, applicationServerKey: expect.any(Uint8Array) }),
    );
    expect(mockedPost).toHaveBeenCalledWith(
      "/api/push/subscribe",
      expect.objectContaining({ body: expect.objectContaining({ endpoint: "https://push.example/abc" }) }),
    );
  });

  it("starts already on when the browser has a saved subscription", async () => {
    stubPushApi({ alreadySubscribed: true });
    render(<PushAlerts />);
    await waitFor(() => expect(screen.getByText("Alerts on")).toBeTruthy());
  });

  it("unsubscribes on click when alerts are already on", async () => {
    const { subscription } = stubPushApi({ alreadySubscribed: true });
    render(<PushAlerts />);
    await waitFor(() => expect(screen.getByText("Alerts on")).toBeTruthy());

    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByText("Killshot alerts")).toBeTruthy());
    expect(subscription.unsubscribe).toHaveBeenCalled();
    expect(mockedPost).toHaveBeenCalledWith("/api/push/unsubscribe", { body: { endpoint: subscription.endpoint } });
  });

  it("shows blocked when the browser denies notification permission", async () => {
    stubPushApi();
    vi.stubGlobal("Notification", { requestPermission: vi.fn().mockResolvedValue("denied") });
    render(<PushAlerts />);
    await waitFor(() => expect(screen.getByText("Killshot alerts")).toBeTruthy());

    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByText("Blocked")).toBeTruthy());
  });
});

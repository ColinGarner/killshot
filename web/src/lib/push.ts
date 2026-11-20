// Web push: a fan subscribes once in the browser; the worker sends a push
// whenever a new killshot (a 10+ point run, by either team) shows up in a
// live game (see killshot/push.py and public/sw.js).
//
// Needs a browser that supports the Push API in an ordinary tab (desktop
// Chrome, Firefox, Edge; Android Chrome). iOS Safari only allows push once
// the site is added to the home screen, which this doesn't set up yet.
import { api } from "../api/client";

const SW_PATH = "/sw.js";

export function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** The existing subscription, if this browser already has one. */
export async function getSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.register(SW_PATH);
  return registration.pushManager.getSubscription();
}

/** Ask for notification permission and subscribe. Throws if permission is denied. */
export async function subscribe(vapidPublicKey: string): Promise<PushSubscription> {
  const registration = await navigator.serviceWorker.register(SW_PATH);
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("blocked");
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    // TypeScript's DOM lib wants a Uint8Array<ArrayBuffer> specifically; a plain Uint8Array
    // (what atob-decoded bytes give us) is a BufferSource at runtime either way.
    applicationServerKey: toUint8Array(vapidPublicKey) as BufferSource,
  });
  await api.POST("/api/push/subscribe", { body: toBody(subscription) });
  return subscription;
}

export async function unsubscribe(subscription: PushSubscription): Promise<void> {
  const { endpoint } = toBody(subscription);
  await subscription.unsubscribe();
  await api.POST("/api/push/unsubscribe", { body: { endpoint } });
}

function toBody(subscription: PushSubscription) {
  return {
    endpoint: subscription.endpoint,
    keys: { p256dh: toBase64Url(subscription.getKey("p256dh")), auth: toBase64Url(subscription.getKey("auth")) },
  };
}

function toBase64Url(key: ArrayBuffer | null): string {
  if (!key) return "";
  let binary = "";
  for (const byte of new Uint8Array(key)) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** The VAPID public key, as the server hands it out (url-safe base64), into the
 * raw byte array `PushManager.subscribe` wants. */
function toUint8Array(base64url: string): Uint8Array {
  const padded = base64url.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(base64url.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

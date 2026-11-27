/**
 * Pure helpers for the Shared Album Mgmt sidebar panel.
 *
 * Everything here is free of DOM and Home Assistant objects so the Node
 * tests (tests/panel.test.mjs) can import it directly. The Lit element in
 * panel.js only renders what these functions decide.
 */

/** Plain-language text for every error key the integration records. */
export const ERROR_TEXT = {
  invalid_link:
    "That isn't a public iCloud shared album link. In Photos, open the shared album, turn on Public Website, and copy its link.",
  album_not_found:
    "Apple doesn't have an album at that link. Its Public Website may have been turned off, or the album was deleted.",
  album_requires_login:
    "This album is shared with people only. Turn on Public Website for it in Photos.",
  apple_error: "Apple sent an answer that couldn't be read. Try again in a few minutes.",
  cannot_connect: "Couldn't reach iCloud. Check Home Assistant's internet connection.",
  incomplete_listing:
    "Apple stopped part way through the album, so nothing was removed. Try again in a few minutes.",
  untrusted_host:
    "Apple returned an unexpected {kind} host, {host}. If it belongs to Apple, trust it here, from Repairs, or under Settings > Advanced > Extra trusted hosts.",
  low_disk_space:
    "Not enough disk space: {free} MB free, {needed} MB needed. Nothing was downloaded.",
  download_failed: "{count} file(s) couldn't be downloaded. They'll be tried again next sync.",
  storage_error: "The album folder couldn't be written: {error}.",
  already_configured: "This album has already been added.",
  invalid_folder: "Use a folder inside the media folder, like shared_albums/family.",
  public_folder:
    "That folder is inside www, which Home Assistant shares without a login. Pick a media folder, like shared_albums/family.",
  invalid_host: "Enter host names like p99-ckdatabasews.icloud.com or *.icloud-content.com.",
  unknown: "Something unexpected went wrong. Check the logs.",
};

/** Notes a sync can leave even when it succeeded. */
export const WARNING_TEXT = {
  baseline_pending:
    "First full read recorded. From now on, photos that leave the album are handled by your setting.",
  empty_listing: "Apple returned an empty album, so nothing was removed.",
  mass_removal_held:
    "Most of the album seems to have disappeared at once. Nothing was removed; the next sync must agree first.",
};

export const PHOTO_FORMATS = [
  ["convert", "Convert HEIC to JPEG", "Largest version; HEIC becomes JPEG."],
  ["original", "Keep originals as-is", "Largest version, exactly as Apple stores it."],
  ["dashboard", "Apple's smaller JPEG", "About 2048 px, smallest files, for dashboards."],
];

export const LEAVE_MODES = [
  ["quarantine", "Quarantine", "Move to a hidden .quarantine folder you can restore from."],
  ["keep", "Keep", "Leave the file where it is."],
  ["delete", "Delete", "Remove the file."],
];

/**
 * Fill {placeholders} in a message.
 * @param {string} template
 * @param {Record<string, string>} [values]
 */
export function fill(template, values = {}) {
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    key in values ? String(values[key]) : match,
  );
}

/**
 * @param {string | null | undefined} key
 * @param {Record<string, string>} [placeholders]
 * @returns {string | null}
 */
export function errorMessage(key, placeholders = {}) {
  if (!key) return null;
  return fill(ERROR_TEXT[key] ?? ERROR_TEXT.unknown, placeholders);
}

/** @param {string} key */
export function warningMessage(key) {
  return WARNING_TEXT[key] ?? key;
}

/**
 * Human-readable size: 0 B, 812 KB, 4.3 MB, 1.25 GB.
 * @param {number} bytes
 */
export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const digits = size >= 100 || unit === 0 ? 0 : size >= 10 ? 1 : 2;
  return `${Number(size.toFixed(digits))} ${units[unit]}`;
}

/**
 * "just now", "5 minutes ago", "3 hours ago", "2 days ago", or "never".
 * @param {string | null | undefined} iso
 * @param {number} [now] epoch ms
 */
export function relativeTime(iso, now = Date.now()) {
  if (!iso) return "never";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "never";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 45) return "just now";
  const steps = [
    [60, "minute"],
    [60, "hour"],
    [24, "day"],
  ];
  let amount = seconds / 60;
  let unit = "minute";
  for (let i = 1; i < steps.length && amount >= steps[i][0]; i += 1) {
    amount /= steps[i][0];
    unit = steps[i][1];
  }
  const rounded = Math.round(amount);
  return `${rounded} ${unit}${rounded === 1 ? "" : "s"} ago`;
}

/**
 * Progress bar width in percent. A known total shows real progress; a sync
 * that hasn't planned yet (total 0) shows an indeterminate bar (null).
 * @param {{done: number, total: number} | null | undefined} progress
 * @returns {number | null}
 */
export function progressPercent(progress) {
  if (!progress || !progress.total) return null;
  return Math.min(100, Math.max(0, Math.round((progress.done / progress.total) * 100)));
}

/**
 * Status chip for an album.
 * @param {{state?: string, syncing?: boolean, last_error?: string | null}} album
 * @returns {{label: string, tone: "ok" | "busy" | "error" | "off"}}
 */
export function statusChip(album) {
  if (album.state && album.state !== "loaded") {
    return { label: "Not running", tone: "off" };
  }
  if (album.syncing) return { label: "Syncing", tone: "busy" };
  if (album.last_error) return { label: "Needs attention", tone: "error" };
  return { label: "Up to date", tone: "ok" };
}

/** "Every 3 hours", "Every 45 minutes", "Manual only". */
export function intervalLabel(minutes) {
  const value = Number(minutes) || 0;
  if (!value) return "Manual only";
  if (value % 1440 === 0) return value === 1440 ? "Every day" : `Every ${value / 1440} days`;
  if (value % 60 === 0) return value === 60 ? "Every hour" : `Every ${value / 60} hours`;
  return `Every ${value} minutes`;
}

/**
 * Same rules as homeassistant.util.slugify for plain names.
 * @param {string} text
 */
export function slugify(text) {
  return (
    String(text || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "album"
  );
}

/** Default folder for a new album name. */
export function defaultFolder(name) {
  return `shared_albums/${slugify(name)}`;
}

/**
 * Quick client-side check that mirrors links.py, so the Add button can say
 * "that isn't an album link" before asking Home Assistant.
 * @param {string} text
 */
export function looksLikeAlbumLink(text) {
  let value = String(text || "").trim();
  if (!value) return false;
  if (!value.includes("://")) value = `https://${value}`;
  let url;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  const host = url.hostname.toLowerCase();
  if (host === "photos.icloud.com" || host === "photos.icloud.com.cn") {
    return /^\/shared\/(album|gallery)\/[A-Za-z0-9_-]{5,64}\/?$/.test(url.pathname);
  }
  if (/^(www\.)?icloud\.com(\.cn)?$/.test(host)) {
    return url.pathname.startsWith("/sharedalbum") && /^#[A-Za-z0-9_-]{5,64}/.test(url.hash);
  }
  return false;
}

/**
 * Turn the settings form into the options the websocket API expects:
 * numbers as numbers, hosts as a list.
 * @param {Record<string, unknown>} form
 */
export function settingsPayload(form) {
  const numbers = [
    "interval_minutes",
    "keep_days",
    "max_files",
    "min_file_size_kb",
    "min_long_edge",
    "max_concurrent_downloads",
    "min_free_space_mb",
    "jpeg_quality",
  ];
  const out = { ...form };
  for (const key of numbers) {
    if (key in out) out[key] = Number(out[key]);
  }
  if (typeof out.extra_trusted_hosts === "string") {
    out.extra_trusted_hosts = out.extra_trusted_hosts
      .split(/[\s,]+/)
      .map((h) => h.trim())
      .filter(Boolean);
  }
  return out;
}

/**
 * Media browser link for a media-source id, so "Open in Media" lands in the
 * album folder.
 * @param {string | null | undefined} mediaContentId
 */
export function mediaBrowserUrl(mediaContentId) {
  const root = encodeURIComponent("app,media-source://media_source");
  if (!mediaContentId) return `/media-browser/browser/${root}`;
  return `/media-browser/browser/${root}/${encodeURIComponent(`directory,${mediaContentId}`)}`;
}

/**
 * Toggle an id in a selection, returning a new Set.
 * @param {Set<string>} selection
 * @param {string} id
 */
export function toggleSelection(selection, id) {
  const next = new Set(selection);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/**
 * The panel shows no entity states, so an update where only `hass` changed
 * (it changes on every state change in Home Assistant) is skipped.
 * @param {Map<string, unknown>} changed
 */
export function needsDraw(changed) {
  if (changed.size === 0) return false;
  return !(changed.size === 1 && changed.has("hass"));
}

/**
 * Album the panel should show: the remembered one if it still exists,
 * otherwise the first.
 * @param {{entry_id: string}[]} albums
 * @param {string | null} selected
 */
export function pickAlbum(albums, selected) {
  if (!albums.length) return null;
  return albums.find((a) => a.entry_id === selected)?.entry_id ?? albums[0].entry_id;
}

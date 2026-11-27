import { LitElement, css, html, nothing } from "lit";

import {
  LEAVE_MODES,
  PHOTO_FORMATS,
  defaultFolder,
  errorMessage,
  formatBytes,
  intervalLabel,
  looksLikeAlbumLink,
  mediaBrowserUrl,
  needsDraw,
  pickAlbum,
  progressPercent,
  relativeTime,
  settingsPayload,
  statusChip,
  toggleSelection,
  warningMessage,
} from "./logic.mjs";

const DOMAIN = "shared_album_mgmt";
const PAGE = 120;

/**
 * Admin sidebar panel: one tab per public shared album.
 *
 * Data comes from the integration's admin-only websocket API:
 * `shared_album_mgmt/subscribe` streams every album's status and progress,
 * and the Photos and Quarantine views ask for pages of files with signed
 * image URLs. Settings are validated by Home Assistant with the same rules
 * as the options flow; field errors come back and are shown inline.
 */
class SharedAlbumMgmtPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    panel: { attribute: false },
    _data: { state: true },
    _selected: { state: true },
    _view: { state: true },
    _items: { state: true },
    _itemsTotal: { state: true },
    _media: { state: true },
    _quarantine: { state: true },
    _picked: { state: true },
    _form: { state: true },
    _formErrors: { state: true },
    _saving: { state: true },
    _adding: { state: true },
    _add: { state: true },
    _toast: { state: true },
    _preview: { state: true },
  };

  constructor() {
    super();
    this._data = null;
    this._selected = localStorage.getItem(`${DOMAIN}:album`) || null;
    this._view = "photos";
    this._items = [];
    this._itemsTotal = 0;
    this._media = "all";
    this._quarantine = [];
    this._picked = new Set();
    this._form = null;
    this._formErrors = {};
    this._saving = false;
    this._adding = false;
    this._add = this._emptyAdd();
    this._toast = null;
    this._preview = null;
    this._unsub = null;
    this._loadedFor = null;
  }

  _emptyAdd() {
    return { url: "", name: "", folder: "", media_dir: "", check: null, busy: false, hosts: [] };
  }

  connectedCallback() {
    super.connectedCallback();
    this._subscribe();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
  }

  shouldUpdate(changed) {
    if (changed.has("hass") && !this._unsub && this.hass) this._subscribe();
    return needsDraw(changed);
  }

  _subscribe() {
    if (!this.hass || this._unsub) return;
    this._unsub = this.hass.connection.subscribeMessage(
      (data) => this._onData(data),
      { type: `${DOMAIN}/subscribe` },
    );
  }

  _onData(data) {
    const previous = this._album;
    this._data = data;
    const selected = pickAlbum(data.albums, this._selected);
    if (selected !== this._selected) this._select(selected);
    const album = this._album;
    // Refresh the open grid when a sync finishes or counts change.
    if (
      album &&
      previous &&
      previous.entry_id === album.entry_id &&
      (previous.syncing !== album.syncing ||
        previous.item_count !== album.item_count ||
        previous.quarantine_count !== album.quarantine_count)
    ) {
      this._loadView();
    } else if (album && this._loadedFor !== album.entry_id) {
      this._loadView();
    }
  }

  get _album() {
    return this._data?.albums.find((a) => a.entry_id === this._selected) ?? null;
  }

  _select(entryId) {
    this._selected = entryId;
    if (entryId) localStorage.setItem(`${DOMAIN}:album`, entryId);
    this._items = [];
    this._quarantine = [];
    this._picked = new Set();
    this._form = null;
    this._formErrors = {};
    this._loadedFor = null;
    if (entryId && this._data) this._loadView();
  }

  async _ws(message) {
    return this.hass.connection.sendMessagePromise(message);
  }

  async _loadView() {
    const album = this._album;
    if (!album || album.state !== "loaded") return;
    this._loadedFor = album.entry_id;
    if (this._view === "photos") {
      const result = await this._ws({
        type: `${DOMAIN}/items`,
        entry_id: album.entry_id,
        offset: 0,
        limit: Math.max(PAGE, this._items.length),
        media: this._media,
      });
      this._items = result.items;
      this._itemsTotal = result.total;
    } else if (this._view === "quarantine") {
      const result = await this._ws({ type: `${DOMAIN}/quarantine`, entry_id: album.entry_id });
      this._quarantine = result.items;
      const ids = new Set(result.items.map((i) => i.id));
      this._picked = new Set([...this._picked].filter((id) => ids.has(id)));
    } else if (this._view === "settings" && !this._form) {
      this._form = { title: album.title, ...album.options };
      this._form.extra_trusted_hosts = (album.options.extra_trusted_hosts || []).join("\n");
    }
  }

  async _more() {
    const album = this._album;
    const result = await this._ws({
      type: `${DOMAIN}/items`,
      entry_id: album.entry_id,
      offset: this._items.length,
      limit: PAGE,
      media: this._media,
    });
    this._items = [...this._items, ...result.items];
    this._itemsTotal = result.total;
  }

  _setView(view) {
    this._view = view;
    this._loadView();
  }

  _notify(text) {
    this._toast = text;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = null;
    }, 4000);
  }

  async _sync(full = false) {
    const result = await this._ws({ type: `${DOMAIN}/sync`, entry_id: this._selected, full });
    this._notify(result.started ? (full ? "Checking every file…" : "Sync started") : "Already syncing");
  }

  async _restore(ids) {
    const result = await this._ws({ type: `${DOMAIN}/restore`, entry_id: this._selected, ids });
    this._notify(`Restored ${result.restored.length} file(s). They'll be kept even though they left the album.`);
    this._picked = new Set();
    this._loadView();
  }

  async _deleteQuarantined(ids) {
    if (!confirm(`Delete ${ids.length} file(s) for good? This can't be undone.`)) return;
    const result = await this._ws({
      type: `${DOMAIN}/delete_quarantined`,
      entry_id: this._selected,
      ids,
    });
    this._notify(`Deleted ${result.deleted} file(s).`);
    this._picked = new Set();
    this._loadView();
  }

  async _trustHost(album, host) {
    const hosts = [...(album.options.extra_trusted_hosts || [])];
    if (!hosts.includes(host)) hosts.push(host);
    const result = await this._ws({
      type: `${DOMAIN}/update_settings`,
      entry_id: album.entry_id,
      options: { extra_trusted_hosts: hosts },
    });
    this._notify(
      result.ok ? `Trusted ${host}. The album reloads and syncs again.` : errorMessage("invalid_host"),
    );
  }

  async _remove() {
    const album = this._album;
    if (
      !confirm(
        `Remove ${album.title}? Syncing stops. The folder and its photos stay on disk.`,
      )
    )
      return;
    await this._ws({ type: `${DOMAIN}/remove_album`, entry_id: album.entry_id });
    this._select(null);
  }

  async _save() {
    this._saving = true;
    const { title, ...rest } = this._form;
    try {
      const result = await this._ws({
        type: `${DOMAIN}/update_settings`,
        entry_id: this._selected,
        title,
        options: settingsPayload(rest),
      });
      if (result.ok) {
        this._formErrors = {};
        this._form = null;
        this._notify("Settings saved. The album reloads with them.");
        this._view = "photos";
      } else {
        this._formErrors = result.errors;
      }
    } finally {
      this._saving = false;
    }
  }

  async _checkLink() {
    const add = this._add;
    if (!looksLikeAlbumLink(add.url)) {
      this._add = { ...add, check: { ok: false, error: "invalid_link" } };
      return;
    }
    this._add = { ...add, busy: true, check: null };
    const request = { type: `${DOMAIN}/validate_link`, url: add.url };
    if (add.hosts?.length) request.extra_trusted_hosts = add.hosts;
    const check = await this._ws(request);
    const name = add.name || check.name || "";
    this._add = {
      ...this._add,
      busy: false,
      check,
      name,
      folder: add.folder || defaultFolder(name || "album"),
    };
  }

  async _addAlbum() {
    const add = this._add;
    this._add = { ...add, busy: true };
    const message = { type: `${DOMAIN}/add_album`, url: add.url };
    if (add.name) message.name = add.name;
    if (add.folder) message.folder = add.folder;
    if (add.media_dir) message.media_dir = add.media_dir;
    if (add.hosts?.length) message.extra_trusted_hosts = add.hosts;
    const result = await this._ws(message);
    if (result.ok) {
      this._adding = false;
      this._add = this._emptyAdd();
      this._select(result.entry_id);
      this._notify("Album added. The first sync is running.");
    } else {
      this._add = { ...this._add, busy: false, check: { ok: false, ...result } };
    }
  }

  // --- rendering -------------------------------------------------------------

  render() {
    if (!this._data) {
      return html`<div class="page"><div class="loading">Loading albums…</div></div>`;
    }
    const albums = this._data.albums;
    return html`
      <div class="page">
        <header>
          <div class="title">
            ${this.narrow
              ? html`<button
                  class="icon menu"
                  aria-label="Open the sidebar"
                  @click=${() =>
                    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }))}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
                  </svg>
                </button>`
              : nothing}
            <svg viewBox="0 0 24 24" class="logo" aria-hidden="true">
              <path
                d="M22,16V4A2,2 0 0,0 20,2H8A2,2 0 0,0 6,4V16A2,2 0 0,0 8,18H20A2,2 0 0,0 22,16M11,12L13.03,14.71L16,11L20,16H8M2,6V20A2,2 0 0,0 4,22H18V20H4V6"
              />
            </svg>
            <h1>Shared Album Mgmt</h1>
          </div>
          <button class="primary" @click=${() => (this._adding = !this._adding)}>
            ${this._adding ? "Close" : "+ Add album"}
          </button>
        </header>
        ${this._adding || !albums.length ? this._renderAdd(!albums.length) : nothing}
        ${albums.length
          ? html`
              <nav class="tabs" role="tablist">
                ${albums.map((album) => {
                  const chip = statusChip(album);
                  return html`<button
                    role="tab"
                    class="tab ${album.entry_id === this._selected ? "active" : ""}"
                    @click=${() => this._select(album.entry_id)}
                  >
                    <span class="dot ${chip.tone}"></span>${album.title}
                  </button>`;
                })}
              </nav>
              ${this._album ? this._renderAlbum(this._album) : nothing}
            `
          : nothing}
        ${this._preview ? this._renderPreview() : nothing}
        ${this._toast ? html`<div class="toast" role="status">${this._toast}</div>` : nothing}
      </div>
    `;
  }

  _renderAdd(first) {
    const add = this._add;
    const check = add.check;
    const dirs = this._data.media_dirs;
    return html`
      <section class="card add">
        <h2>${first ? "Add your first shared album" : "Add a shared album"}</h2>
        <p class="muted">
          In Photos, open the shared album, turn on <b>Public Website</b>, and copy its link.
          Both <code>photos.icloud.com/shared/album/…</code> and older
          <code>icloud.com/sharedalbum/#…</code> links work. Anyone with the link can see the
          album, so treat it like a password.
        </p>
        <label
          >Public album link
          <input
            type="url"
            placeholder="https://photos.icloud.com/shared/album/…"
            .value=${add.url}
            @input=${(e) => (this._add = { ...add, url: e.target.value, check: null })}
          />
        </label>
        <div class="row">
          <button ?disabled=${!add.url || add.busy} @click=${this._checkLink}>
            ${add.busy && !check ? "Checking…" : "Check link"}
          </button>
          ${check && !check.ok
            ? html`<span class="error-text">${errorMessage(check.error, check.placeholders)}</span>`
            : nothing}
          ${check?.error === "untrusted_host" && check.placeholders?.host
            ? html`<button
                @click=${() => {
                  this._add = { ...this._add, hosts: [...(this._add.hosts || []), check.placeholders.host] };
                  this._checkLink();
                }}
              >
                Trust ${check.placeholders.host}
              </button>`
            : nothing}
          ${check?.ok
            ? html`<span class="ok-text"
                >Found ${check.name ? html`<b>${check.name}</b>` : "the album"}: ${check.photos}
                photos, ${check.videos} videos${check.already_added
                  ? " (already added)"
                  : ""}</span
              >`
            : nothing}
        </div>
        ${check?.ok && !check.already_added
          ? html`
              <div class="grid2">
                <label
                  >Name
                  <input
                    .value=${add.name}
                    @input=${(e) => (this._add = { ...this._add, name: e.target.value })}
                  />
                </label>
                <label
                  >Media folder
                  <select
                    @change=${(e) => (this._add = { ...this._add, media_dir: e.target.value })}
                  >
                    ${dirs.map(
                      (d) => html`<option value=${d} ?selected=${(add.media_dir || dirs[0]) === d}>${d}</option>`,
                    )}
                  </select>
                </label>
                <label class="span2"
                  >Folder
                  <input
                    .value=${add.folder}
                    @input=${(e) => (this._add = { ...this._add, folder: e.target.value })}
                  />
                </label>
              </div>
              <p class="muted">
                New albums convert HEIC to JPEG, quarantine photos that leave the album, and sync
                every 3 hours. Change any of it under Settings after adding.
              </p>
              <button class="primary" ?disabled=${add.busy} @click=${this._addAlbum}>
                ${add.busy ? "Adding…" : "Add album"}
              </button>
            `
          : nothing}
      </section>
    `;
  }

  _renderAlbum(album) {
    const chip = statusChip(album);
    if (album.state !== "loaded") {
      return html`<section class="card">
        <h2>${album.title}</h2>
        <p>This album isn't running (${album.state}). Check it under Settings > Devices &amp; services.</p>
      </section>`;
    }
    const percent = progressPercent(album.progress);
    const error = errorMessage(album.last_error, album.last_error_placeholders);
    const warnings = album.last_result?.warnings ?? [];
    return html`
      <section class="card status">
        <div class="hero">
          ${album.latest_thumb
            ? html`<img class="latest" src=${album.latest_thumb} alt="Latest photo" />`
            : html`<div class="latest empty">No photos yet</div>`}
          <div class="summary">
            <div class="row between">
              <h2>${album.title}</h2>
              <span class="chip ${chip.tone}">${chip.label}</span>
            </div>
            <div class="muted small">
              ${album.kind === "modern" ? "photos.icloud.com link" : "icloud.com/sharedalbum link"}
              · id ${album.album_id} · ${intervalLabel(album.interval)}
            </div>
            ${album.syncing
              ? html`<div class="progress" aria-label="Sync progress">
                    <div
                      class="bar ${percent === null ? "indeterminate" : ""}"
                      style="width:${percent === null ? 30 : percent}%"
                    ></div>
                  </div>
                  <div class="small muted">
                    ${album.progress?.total
                      ? `${album.progress.done} of ${album.progress.total} downloaded${album.progress.current ? ` · ${album.progress.current}` : ""}`
                      : "Reading the album from iCloud…"}
                  </div>`
              : nothing}
            <dl class="stats">
              <div><dt>Items</dt><dd>${album.item_count}</dd></div>
              <div><dt>Photos</dt><dd>${album.photo_count}</dd></div>
              <div><dt>Videos</dt><dd>${album.video_count}</dd></div>
              <div><dt>In album</dt><dd>${album.remote_count}</dd></div>
              <div><dt>Space used</dt><dd>${formatBytes(album.bytes_used)}</dd></div>
              <div><dt>Quarantined</dt><dd>${album.quarantine_count}</dd></div>
              <div><dt>Last sync</dt><dd title=${album.last_sync ?? ""}>${relativeTime(album.last_sync)}</dd></div>
            </dl>
            <div class="folder small"><span class="muted">Folder</span> <code>${album.folder}</code></div>
          </div>
        </div>
        ${error
          ? html`<div class="banner error">
              ${error}
              ${album.last_error === "untrusted_host" && album.last_error_placeholders?.host
                ? html`<div class="row">
                    <button @click=${() => this._trustHost(album, album.last_error_placeholders.host)}>
                      Trust ${album.last_error_placeholders.host}
                    </button>
                  </div>`
                : nothing}
            </div>`
          : nothing}
        ${warnings.map((w) => html`<div class="banner info">${warningMessage(w)}</div>`)}
        <div class="row actions">
          <button class="primary" ?disabled=${album.syncing} @click=${() => this._sync(false)}>
            Sync now
          </button>
          <button ?disabled=${album.syncing} @click=${() => this._sync(true)}>Check every file</button>
          <a class="button" href=${mediaBrowserUrl(album.media_content_id)}>Open in Media</a>
          <span class="spacer"></span>
          <button class="danger flat" @click=${this._remove}>Remove album</button>
        </div>
      </section>
      <nav class="subtabs">
        ${[
          ["photos", `Photos (${album.item_count})`],
          ["quarantine", `Quarantine (${album.quarantine_count})`],
          ["settings", "Settings"],
        ].map(
          ([key, label]) =>
            html`<button class=${this._view === key ? "active" : ""} @click=${() => this._setView(key)}>
              ${label}
            </button>`,
        )}
      </nav>
      ${this._view === "photos" ? this._renderPhotos() : nothing}
      ${this._view === "quarantine" ? this._renderQuarantine() : nothing}
      ${this._view === "settings" ? this._renderSettings(album) : nothing}
    `;
  }

  _thumb(item, extra = nothing) {
    const video = item.media_type === "video";
    return html`<figure class="thumb ${video ? "video" : ""}">
      <button class="img" @click=${() => (this._preview = item)} title=${item.file}>
        ${video
          ? html`<svg viewBox="0 0 24 24"><path d="M8,5.14V19.14L19,12.14L8,5.14Z" /></svg>`
          : html`<img loading="lazy" src=${item.thumb} alt=${item.file} />`}
      </button>
      ${extra}
      <figcaption>
        <span class="name">${item.file}</span>
        <span class="muted">${item.captured_at ? item.captured_at.slice(0, 10) : ""} · ${formatBytes(item.size)}</span>
        ${item.pinned ? html`<span class="tag">kept</span>` : item.in_album === false ? html`<span class="tag">left album</span>` : nothing}
      </figcaption>
    </figure>`;
  }

  _renderPhotos() {
    return html`
      <section class="card">
        <div class="row between">
          <div class="segmented">
            ${[
              ["all", "All"],
              ["image", "Photos"],
              ["video", "Videos"],
            ].map(
              ([key, label]) => html`<button
                class=${this._media === key ? "active" : ""}
                @click=${() => {
                  this._media = key;
                  this._items = [];
                  this._loadView();
                }}
              >
                ${label}
              </button>`,
            )}
          </div>
          <span class="muted small">${this._itemsTotal} file(s)</span>
        </div>
        ${this._items.length
          ? html`<div class="grid">${this._items.map((item) => this._thumb(item))}</div>`
          : html`<p class="muted center">Nothing here yet. Files appear as soon as the first sync downloads them.</p>`}
        ${this._items.length < this._itemsTotal
          ? html`<div class="center"><button @click=${this._more}>Load more</button></div>`
          : nothing}
      </section>
    `;
  }

  _renderQuarantine() {
    const items = this._quarantine;
    const picked = [...this._picked];
    return html`
      <section class="card">
        <p class="muted">
          Photos that left the album are moved here instead of being deleted. Restore puts a file
          back in the album folder and keeps it there for good; Delete removes it.
        </p>
        ${items.length
          ? html`
              <div class="row">
                <button
                  @click=${() =>
                    (this._picked =
                      picked.length === items.length ? new Set() : new Set(items.map((i) => i.id)))}
                >
                  ${picked.length === items.length ? "Select none" : "Select all"}
                </button>
                <button ?disabled=${!picked.length} @click=${() => this._restore(picked)}>
                  Restore ${picked.length || ""}
                </button>
                <button class="danger" ?disabled=${!picked.length} @click=${() => this._deleteQuarantined(picked)}>
                  Delete ${picked.length || ""}
                </button>
              </div>
              <div class="grid">
                ${items.map((item) =>
                  this._thumb(
                    item,
                    html`<label class="pick"
                      ><input
                        type="checkbox"
                        .checked=${this._picked.has(item.id)}
                        @change=${() => (this._picked = toggleSelection(this._picked, item.id))}
                      />
                      <span class="small">moved ${relativeTime(item.moved_at)}</span></label
                    >`,
                  ),
                )}
              </div>
            `
          : html`<p class="muted center">The quarantine is empty.</p>`}
      </section>
    `;
  }

  _field(key, label, help, input) {
    const err = this._formErrors[key];
    return html`<label class=${err ? "invalid" : ""}
      >${label} ${input} ${help ? html`<span class="help">${help}</span>` : nothing}
      ${err ? html`<span class="error-text">${this._fieldError(err)}</span>` : nothing}
    </label>`;
  }

  _fieldError(key) {
    return (
      {
        invalid_interval: "Use 0 for manual only, or 15 to 10080 minutes.",
        nothing_to_sync: "Turn on photos, videos, or both.",
        invalid_media_dir: "Choose one of Home Assistant's media folders.",
        invalid_folder: "Use a folder like shared_albums/family. Each part starts with a letter or digit.",
        public_folder: "That folder is inside www, which Home Assistant shares without a login. Pick a media folder, like shared_albums/family.",
        invalid_number: "Enter a number in the allowed range.",
        invalid_host: "Use host names like p99-ckdatabasews.icloud.com or *.icloud-content.com.",
      }[key] ?? key
    );
  }

  _bind(key, kind = "text") {
    return (e) => {
      const value = kind === "bool" ? e.target.checked : e.target.value;
      this._form = { ...this._form, [key]: value };
    };
  }

  _number(key, min, max, step = 1) {
    return html`<input
      type="number"
      min=${min}
      max=${max}
      step=${step}
      .value=${String(this._form[key] ?? "")}
      @input=${this._bind(key)}
    />`;
  }

  _choices(key, choices) {
    return html`<div class="choices">
      ${choices.map(
        ([value, label, help]) => html`<label class="choice ${this._form[key] === value ? "on" : ""}">
          <input
            type="radio"
            name=${key}
            .checked=${this._form[key] === value}
            @change=${() => (this._form = { ...this._form, [key]: value })}
          />
          <span><b>${label}</b><br /><span class="muted small">${help}</span></span>
        </label>`,
      )}
    </div>`;
  }

  _renderSettings(album) {
    const f = this._form;
    if (!f) return html`<section class="card"><p class="muted">Loading…</p></section>`;
    const heic = this._data.heic_available;
    return html`
      <section class="card settings">
        <h3>Album</h3>
        <div class="grid2">
          ${this._field("title", "Name", null, html`<input .value=${f.title} @input=${this._bind("title")} />`)}
          ${this._field(
            "interval_minutes",
            "Sync every (minutes)",
            "0 = only when you press Sync now.",
            this._number("interval_minutes", 0, 10080, 5),
          )}
        </div>
        <h3>Photo format</h3>
        ${this._choices("photo_format", PHOTO_FORMATS)}
        ${!heic && f.photo_format === "convert"
          ? html`<div class="banner info">
              HEIC conversion isn't available on this system, so Apple's largest JPEG is saved instead.
            </div>`
          : nothing}
        <h3>When a photo leaves the album</h3>
        ${this._choices("leave_mode", LEAVE_MODES)}
        <p class="muted small">
          Nothing is removed before the first full read of the album, when Apple returns an empty
          album, or when most of the album disappears at once (the next sync must agree). Files you
          changed by hand are never removed.
        </p>
        <h3>What to save</h3>
        <div class="row">
          <label class="toggle"
            ><input type="checkbox" .checked=${f.sync_photos} @change=${this._bind("sync_photos", "bool")} /> Photos</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${f.sync_videos} @change=${this._bind("sync_videos", "bool")} /> Videos</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${f.write_latest} @change=${this._bind("write_latest", "bool")} />
            latest.jpg</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${f.write_index} @change=${this._bind("write_index", "bool")} />
            index.json</label
          >
        </div>
        ${this._formErrors.sync_photos
          ? html`<span class="error-text">${this._fieldError(this._formErrors.sync_photos)}</span>`
          : nothing}
        <h3>Folder</h3>
        <div class="grid2">
          ${this._field(
            "media_dir",
            "Media folder",
            null,
            html`<select @change=${this._bind("media_dir")}>
              ${this._data.media_dirs.map(
                (d) => html`<option value=${d} ?selected=${f.media_dir === d}>${d}</option>`,
              )}
            </select>`,
          )}
          ${this._field(
            "folder",
            "Folder",
            "Changing it starts a new folder; the old one stays as it is.",
            html`<input .value=${f.folder} @input=${this._bind("folder")} />`,
          )}
        </div>
        <details>
          <summary>Limits and filters</summary>
          <div class="grid2">
            ${this._field("keep_days", "Keep days", "Only photos taken in the last N days. 0 = all.", this._number("keep_days", 0, 36500))}
            ${this._field("max_files", "Max files", "Only the newest N items. 0 = all.", this._number("max_files", 0, 1000000))}
            ${this._field("min_file_size_kb", "Minimum file size (kB)", "0 = no minimum.", this._number("min_file_size_kb", 0, 1000000))}
            ${this._field("min_long_edge", "Minimum long edge (px)", "0 = no minimum.", this._number("min_long_edge", 0, 20000))}
          </div>
        </details>
        <details>
          <summary>Advanced</summary>
          <div class="grid2">
            ${this._field(
              "extra_trusted_hosts",
              "Extra trusted hosts",
              "One per line. For when Apple starts using a new host. *.example.com covers subdomains.",
              html`<textarea rows="3" .value=${f.extra_trusted_hosts} @input=${this._bind("extra_trusted_hosts")}></textarea>`,
            )}
            ${this._field("max_concurrent_downloads", "Downloads at once", null, this._number("max_concurrent_downloads", 1, 8))}
            ${this._field("min_free_space_mb", "Keep this much disk free (MB)", null, this._number("min_free_space_mb", 0, 10000000))}
            ${this._field("jpeg_quality", "JPEG quality (%)", "For photos converted from HEIC.", this._number("jpeg_quality", 50, 100))}
          </div>
        </details>
        <div class="row actions">
          <button class="primary" ?disabled=${this._saving} @click=${this._save}>
            ${this._saving ? "Saving…" : "Save"}
          </button>
          <button
            class="flat"
            @click=${() => {
              this._form = null;
              this._formErrors = {};
              this._loadView();
            }}
          >
            Reset
          </button>
        </div>
      </section>
    `;
  }

  _renderPreview() {
    const item = this._preview;
    return html`<div class="overlay" @click=${() => (this._preview = null)}>
      <div class="viewer" @click=${(e) => e.stopPropagation()}>
        ${item.media_type === "video"
          ? html`<video src=${item.full} controls autoplay></video>`
          : html`<img src=${item.full} alt=${item.file} />`}
        <div class="row between">
          <span>${item.file}</span>
          <button class="flat" @click=${() => (this._preview = null)}>Close</button>
        </div>
      </div>
    </div>`;
  }

  static styles = css`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--primary-background-color, #f5f6f8);
      color: var(--primary-text-color, #1c1c1e);
      font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
      --accent: var(--primary-color, #03a9f4);
      --card: var(--card-background-color, #fff);
      --muted: var(--secondary-text-color, #6b7280);
      --line: var(--divider-color, rgba(0, 0, 0, 0.12));
      --ok: var(--success-color, #2e7d32);
      --warn: var(--warning-color, #f59e0b);
      --bad: var(--error-color, #d32f2f);
    }
    .page {
      max-width: 1180px;
      margin: 0 auto;
      padding: 16px;
      box-sizing: border-box;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .title {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    button.icon.menu {
      padding: 6px;
      border: none;
      background: transparent;
      line-height: 0;
    }
    button.icon.menu svg {
      width: 24px;
      height: 24px;
      fill: currentColor;
    }
    .logo {
      width: 30px;
      height: 30px;
      fill: var(--accent);
    }
    h1 {
      font-size: 22px;
      font-weight: 500;
      margin: 0;
    }
    h2 {
      font-size: 19px;
      margin: 0;
      font-weight: 500;
    }
    h3 {
      font-size: 15px;
      margin: 18px 0 8px;
      font-weight: 600;
    }
    .card {
      background: var(--card);
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.12));
      padding: 16px;
      margin-bottom: 12px;
    }
    .muted {
      color: var(--muted);
    }
    .small {
      font-size: 13px;
    }
    .center {
      text-align: center;
    }
    code {
      font-size: 12.5px;
      background: rgba(127, 127, 127, 0.12);
      padding: 1px 5px;
      border-radius: 4px;
      word-break: break-all;
    }
    button,
    a.button {
      font: inherit;
      font-size: 14px;
      border: 1px solid var(--line);
      background: var(--card);
      color: var(--primary-text-color);
      border-radius: 18px;
      padding: 7px 16px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    button:disabled {
      opacity: 0.5;
      cursor: default;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    button.danger {
      color: var(--bad);
      border-color: var(--bad);
    }
    button.flat {
      border-color: transparent;
      background: transparent;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .row.between {
      justify-content: space-between;
    }
    .spacer {
      flex: 1;
    }
    .actions {
      margin-top: 14px;
    }
    .tabs {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      margin-bottom: 12px;
      padding-bottom: 2px;
    }
    .tab {
      white-space: nowrap;
    }
    .tab.active {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--muted);
      display: inline-block;
    }
    .dot.ok {
      background: var(--ok);
    }
    .dot.busy {
      background: var(--accent);
      box-shadow: 0 0 0 3px rgba(3, 169, 244, 0.25);
    }
    .dot.error {
      background: var(--bad);
    }
    .tab.active .dot {
      box-shadow: 0 0 0 2px #fff;
    }
    .chip {
      font-size: 12.5px;
      padding: 3px 10px;
      border-radius: 12px;
      background: rgba(127, 127, 127, 0.15);
    }
    .chip.ok {
      background: rgba(46, 125, 50, 0.14);
      color: var(--ok);
    }
    .chip.busy {
      background: rgba(3, 169, 244, 0.14);
      color: var(--accent);
    }
    .chip.error {
      background: rgba(211, 47, 47, 0.12);
      color: var(--bad);
    }
    .hero {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }
    .latest {
      width: 180px;
      height: 180px;
      object-fit: cover;
      border-radius: 10px;
      flex: none;
      background: rgba(127, 127, 127, 0.12);
    }
    .latest.empty {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 13px;
    }
    .summary {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      gap: 8px;
      margin: 4px 0 0;
    }
    .stats div {
      background: rgba(127, 127, 127, 0.07);
      border-radius: 8px;
      padding: 8px 10px;
    }
    dt {
      font-size: 12px;
      color: var(--muted);
    }
    dd {
      margin: 2px 0 0;
      font-size: 18px;
      font-weight: 500;
    }
    .progress {
      height: 8px;
      border-radius: 4px;
      background: rgba(127, 127, 127, 0.18);
      overflow: hidden;
      position: relative;
    }
    .bar {
      height: 100%;
      background: var(--accent);
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .bar.indeterminate {
      position: absolute;
      animation: slide 1.4s infinite ease-in-out;
    }
    @keyframes slide {
      from {
        left: -30%;
      }
      to {
        left: 100%;
      }
    }
    .banner {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 14px;
    }
    .banner.error {
      background: rgba(211, 47, 47, 0.1);
      color: var(--bad);
    }
    .banner.info {
      background: rgba(3, 169, 244, 0.1);
    }
    .subtabs {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      margin: 4px 0 12px;
    }
    .subtabs button {
      border: none;
      border-radius: 0;
      background: transparent;
      padding: 10px 14px;
      border-bottom: 2px solid transparent;
    }
    .subtabs button.active {
      border-bottom-color: var(--accent);
      color: var(--accent);
      font-weight: 500;
    }
    .segmented {
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
    }
    .segmented button {
      border: none;
      border-radius: 0;
    }
    .segmented button.active {
      background: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .thumb {
      margin: 0;
      background: rgba(127, 127, 127, 0.06);
      border-radius: 10px;
      overflow: hidden;
      position: relative;
    }
    .thumb .img {
      border: none;
      padding: 0;
      border-radius: 0;
      width: 100%;
      aspect-ratio: 1;
      background: rgba(127, 127, 127, 0.15);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .thumb.video svg {
      width: 48px;
      height: 48px;
      fill: var(--muted);
    }
    figcaption {
      padding: 6px 8px 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 12px;
    }
    .name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tag {
      align-self: flex-start;
      font-size: 11px;
      background: rgba(245, 158, 11, 0.18);
      border-radius: 6px;
      padding: 1px 6px;
    }
    .pick {
      position: absolute;
      top: 6px;
      left: 6px;
      background: rgba(0, 0, 0, 0.55);
      color: #fff;
      border-radius: 8px;
      padding: 2px 8px 2px 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 13px;
      color: var(--muted);
      margin: 6px 0;
    }
    input,
    select,
    textarea {
      font: inherit;
      font-size: 14px;
      color: var(--primary-text-color);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
    }
    label.invalid input,
    label.invalid select,
    label.invalid textarea {
      border-color: var(--bad);
    }
    .help {
      font-size: 12px;
    }
    .error-text {
      color: var(--bad);
      font-size: 13px;
    }
    .ok-text {
      color: var(--ok);
      font-size: 14px;
    }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0 16px;
    }
    .span2 {
      grid-column: span 2;
    }
    .choices {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 8px;
    }
    .choice {
      flex-direction: row;
      align-items: flex-start;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      color: var(--primary-text-color);
      cursor: pointer;
      margin: 0;
    }
    .choice.on {
      border-color: var(--accent);
      background: rgba(3, 169, 244, 0.07);
    }
    .toggle {
      flex-direction: row;
      align-items: center;
      color: var(--primary-text-color);
      font-size: 14px;
      margin-right: 12px;
    }
    details {
      margin-top: 14px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    summary {
      cursor: pointer;
      font-weight: 600;
      font-size: 15px;
    }
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10;
    }
    .viewer {
      background: var(--card);
      border-radius: 12px;
      padding: 12px;
      max-width: 92vw;
      max-height: 92vh;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .viewer img,
    .viewer video {
      max-width: 88vw;
      max-height: 80vh;
      border-radius: 8px;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: #323232;
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 14px;
      z-index: 11;
    }
    .loading {
      padding: 48px;
      text-align: center;
      color: var(--muted);
    }
    @media (max-width: 700px) {
      .hero {
        flex-direction: column;
      }
      .latest {
        width: 100%;
        height: 200px;
      }
      .grid2 {
        grid-template-columns: 1fr;
      }
      .span2 {
        grid-column: auto;
      }
      .grid {
        grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      }
    }
  `;
}

if (!customElements.get("shared-album-mgmt-panel")) {
  customElements.define("shared-album-mgmt-panel", SharedAlbumMgmtPanel);
}

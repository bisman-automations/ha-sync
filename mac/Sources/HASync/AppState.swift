import EventKit
import Foundation
import ServiceManagement
import SwiftUI

/// Settings, catalogs, sync status and the sync loop.
@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()
    private let d = UserDefaults.standard

    // Connection
    @Published var haURL: String { didSet { d.set(haURL, forKey: "haURL") } }
    @Published var token: String { didSet { Keychain.set(token, for: "token") } }
    @Published var intervalMinutes: Int { didSet { d.set(intervalMinutes, forKey: "interval"); restartLoop() } }

    // Calendar / Reminders
    @Published var calendarIDs: Set<String> { didSet { saveSet(calendarIDs, "calendarIDs"); selectionChanged() } }
    @Published var reminderListIDs: Set<String> { didSet { saveSet(reminderListIDs, "reminderListIDs"); selectionChanged() } }
    @Published var daysBack: Int { didSet { d.set(daysBack, forKey: "daysBack") } }
    @Published var daysAhead: Int { didSet { d.set(daysAhead, forKey: "daysAhead") } }
    @Published var includeCompleted: Bool { didSet { d.set(includeCompleted, forKey: "includeCompleted") } }

    // Photos
    @Published var albumIDs: Set<String> { didSet { saveSet(albumIDs, "albumIDs"); selectionChanged(includePhotos: true) } }
    @Published var maxPhotosPerAlbum: Int { didSet { d.set(maxPhotosPerAlbum, forKey: "maxPhotos") } }
    @Published var maxPixel: Int { didSet { d.set(maxPixel, forKey: "maxPixel") } }

    // Notes
    @Published var noteFolderIDs: Set<String> { didSet { saveSet(noteFolderIDs, "noteFolderIDs"); selectionChanged() } }
    @Published var noteBodyLimit: Int { didSet { d.set(noteBodyLimit, forKey: "noteBodyLimit") } }

    // Catalogs shown in Settings
    @Published var calendarCatalog: [CatalogItem] = []
    @Published var reminderCatalog: [CatalogItem] = []
    @Published var albumCatalog: [CatalogItem] = []
    @Published var noteCatalog: [CatalogItem] = [] { didSet { saveNoteCatalog() } }
    @Published var notesLoading = false
    @Published var notesError: String?

    // Status
    @Published var isSyncing = false
    @Published var progress: String?
    @Published var lastSync: Date?
    @Published var lastErrors: [String] = []
    @Published var connectionStatus: String?

    let eventKit = EventKitSource()
    let photos = PhotosSource()
    let notes = NotesSource()
    private var loopTask: Task<Void, Never>?
    private var debounceTask: Task<Void, Never>?

    private init() {
        haURL = d.string(forKey: "haURL") ?? "http://homeassistant.local:8123"
        token = Keychain.get("token") ?? ""
        intervalMinutes = d.object(forKey: "interval") as? Int ?? 15
        calendarIDs = Set(d.stringArray(forKey: "calendarIDs") ?? [])
        reminderListIDs = Set(d.stringArray(forKey: "reminderListIDs") ?? [])
        daysBack = d.object(forKey: "daysBack") as? Int ?? 7
        daysAhead = d.object(forKey: "daysAhead") as? Int ?? 60
        includeCompleted = d.bool(forKey: "includeCompleted")
        albumIDs = Set(d.stringArray(forKey: "albumIDs") ?? [])
        maxPhotosPerAlbum = d.object(forKey: "maxPhotos") as? Int ?? 300
        maxPixel = d.object(forKey: "maxPixel") as? Int ?? 2048
        noteFolderIDs = Set(d.stringArray(forKey: "noteFolderIDs") ?? [])
        noteBodyLimit = d.object(forKey: "noteBodyLimit") as? Int ?? 2000
        if let data = d.data(forKey: "noteCatalog"),
           let saved = try? JSONDecoder().decode([[String]].self, from: data) {
            noteCatalog = saved.compactMap { $0.count >= 3 ? CatalogItem(id: $0[0], title: $0[1], group: $0[2], detail: $0.count > 3 ? $0[3] : nil) : nil }
        }

        // Re-sync shortly after Calendar/Reminders change.
        NotificationCenter.default.addObserver(forName: .EKEventStoreChanged, object: eventKit.store, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.scheduleSoonSync() }
        }
        refreshLocalCatalogs()
        restartLoop()
    }

    private func saveSet(_ s: Set<String>, _ key: String) { d.set(Array(s), forKey: key) }
    private func saveNoteCatalog() {
        let rows = noteCatalog.map { [$0.id, $0.title, $0.group, $0.detail ?? ""] }
        d.set(try? JSONEncoder().encode(rows), forKey: "noteCatalog")
    }

    var launchAtLogin: Bool {
        get { SMAppService.mainApp.status == .enabled }
        set {
            do { newValue ? try SMAppService.mainApp.register() : try SMAppService.mainApp.unregister() }
            catch { lastErrors = ["Launch at login: \(error.localizedDescription)"] }
            objectWillChange.send()
        }
    }

    // MARK: Catalogs & permissions

    func refreshLocalCatalogs() {
        if eventKit.calendarAuthorized { calendarCatalog = eventKit.catalog(for: .event) }
        if eventKit.remindersAuthorized { reminderCatalog = eventKit.catalog(for: .reminder) }
        if photos.authorized { albumCatalog = photos.catalog() }
    }

    func requestCalendar() async { _ = await eventKit.requestCalendarAccess(); refreshLocalCatalogs() }
    func requestReminders() async { _ = await eventKit.requestRemindersAccess(); refreshLocalCatalogs() }
    func requestPhotos() async { _ = await photos.requestAccess(); refreshLocalCatalogs() }

    func loadNoteFolders() async {
        notesLoading = true
        defer { notesLoading = false }
        do { noteCatalog = try await notes.catalog(); notesError = nil }
        catch { notesError = error.localizedDescription }
    }

    func testConnection() async {
        connectionStatus = "Checking…"
        do { connectionStatus = try await HAClient(urlString: haURL, token: token).check() }
        catch { connectionStatus = error.localizedDescription }
    }

    // MARK: Scheduling

    func restartLoop() {
        loopTask?.cancel()
        let minutes = max(1, intervalMinutes)
        loopTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(5))
            while !Task.isCancelled {
                await self?.syncNow()
                try? await Task.sleep(for: .seconds(minutes * 60))
            }
        }
    }

    private var pendingPhotos = false

    /// Debounced sync. Several quick changes (ticking a few boxes) become one sync.
    private func scheduleSoonSync(after seconds: Int = 10, includePhotos: Bool = false) {
        debounceTask?.cancel()
        pendingPhotos = pendingPhotos || includePhotos
        debounceTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(seconds))
            guard !Task.isCancelled, let self else { return }
            // A sync already running read the old selection; wait for it, then send ours.
            while self.isSyncing {
                try? await Task.sleep(for: .seconds(2))
                if Task.isCancelled { return }
            }
            let photos = self.pendingPhotos
            self.pendingPhotos = false
            await self.syncNow(includePhotos: photos)
        }
    }

    /// A box was ticked or unticked in Settings: send it to Home Assistant soon, so an
    /// unchecked calendar, list, folder or album goes unavailable there (and can be deleted).
    private func selectionChanged(includePhotos: Bool = false) {
        scheduleSoonSync(after: 3, includePhotos: includePhotos)
    }

    // MARK: Sync

    func syncNow(includePhotos: Bool = true) async {
        guard !isSyncing else { return }
        guard let client = try? HAClient(urlString: haURL, token: token) else {
            lastErrors = ["Set your Home Assistant URL and token in Settings."]
            return
        }
        isSyncing = true
        defer { isSyncing = false; progress = nil }
        var errors: [String] = []
        var payload = SyncPayload(source: Host.current().localizedName ?? "Mac")

        // Each section is sent independently; a section that fails is omitted so HA keeps the previous data.
        progress = "Reading Calendar…"
        if eventKit.calendarAuthorized {
            payload.calendars = eventKit.events(calendarIDs: calendarIDs, daysBack: daysBack, daysAhead: daysAhead)
        } else if !calendarIDs.isEmpty { errors.append("Calendar access not granted.") }

        progress = "Reading Reminders…"
        if eventKit.remindersAuthorized {
            payload.reminders = await eventKit.reminders(listIDs: reminderListIDs, includeCompleted: includeCompleted, completedDaysBack: daysBack)
        } else if !reminderListIDs.isEmpty { errors.append("Reminders access not granted.") }

        if noteFolderIDs.isEmpty {
            payload.notes = []
        } else {
            progress = "Reading Notes…"
            let byID = Dictionary(noteCatalog.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
            let folders = noteFolderIDs.map { byID[$0] ?? CatalogItem(id: $0, title: $0, group: "") }
            do { payload.notes = try await notes.fetch(folders: folders, bodyLimit: noteBodyLimit) }
            catch { errors.append(error.localizedDescription) }
        }

        var albums: [String: PhotosSource.Album] = [:]   // slug -> album
        if includePhotos {
            if photos.authorized {
                progress = "Reading Photos…"
                var payloads: [AlbumPayload] = []
                var usedSlugs = Set<String>()
                for id in albumIDs.sorted() {
                    guard let album = photos.album(id: id, limit: maxPhotosPerAlbum) else { continue }
                    let title = album.collection.localizedTitle ?? "Album"
                    var slug = slugify(title), n = 2
                    while usedSlugs.contains(slug) { slug = "\(slugify(title))-\(n)"; n += 1 }
                    usedSlugs.insert(slug)
                    albums[slug] = album
                    payloads.append(AlbumPayload(id: id, title: title, slug: slug, kind: PhotosSource.kind(of: album.collection),
                                                 count: album.total, files: album.files))
                }
                payload.albums = payloads
            } else if !albumIDs.isEmpty { errors.append("Photos access not granted.") }
        }

        do {
            progress = "Sending to Home Assistant…"
            let response = try await client.push(payload)
            let missing = response.missing ?? [:]
            let total = missing.values.reduce(0) { $0 + $1.count }
            if total > 0 {
                var done = 0, failed = 0
                for (slug, files) in missing {
                    guard let album = albums[slug] else { continue }
                    for file in files {
                        done += 1
                        progress = "Uploading photo \(done) of \(total)…"
                        guard let asset = album.assets[file], let jpeg = await photos.jpeg(for: asset, maxPixel: maxPixel) else {
                            failed += 1; continue
                        }
                        do { try await client.uploadPhoto(album: slug, filename: file, jpeg: jpeg) }
                        catch { failed += 1 }
                    }
                }
                if failed > 0 { errors.append("\(failed) photo(s) failed to upload; will retry next sync.") }
                // Second, albums-only push so HA's photo counts reflect what was uploaded.
                _ = try await client.push(SyncPayload(source: payload.source, albums: payload.albums))
            }
            lastSync = Date()
        } catch {
            errors.insert(error.localizedDescription, at: 0)
        }
        lastErrors = errors
    }
}

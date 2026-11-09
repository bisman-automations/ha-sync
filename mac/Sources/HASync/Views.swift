import SwiftUI

struct MenuContent: View {
    @ObservedObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        if let p = state.progress {
            Text(p)
        } else if let last = state.lastSync {
            Text("Last sync: \(last.formatted(date: .omitted, time: .shortened))")
        } else {
            Text("Not synced yet")
        }
        ForEach(state.lastErrors, id: \.self) { Text("⚠︎ \($0)") }
        Divider()
        Button(state.isSyncing ? "Syncing…" : "Sync Now") { Task { await state.syncNow() } }
            .disabled(state.isSyncing)
            .keyboardShortcut("s")
        Button("Settings…") {
            openWindow(id: "settings")
            NSApp.activate(ignoringOtherApps: true)
        }
        .keyboardShortcut(",")
        Divider()
        Button("Quit HA Sync") { NSApp.terminate(nil) }.keyboardShortcut("q")
    }
}

struct SettingsView: View {
    @ObservedObject var state: AppState

    var body: some View {
        TabView {
            ConnectionTab(state: state).tabItem { Label("Home Assistant", systemImage: "house") }
            CalendarTab(state: state).tabItem { Label("Calendar", systemImage: "calendar") }
            RemindersTab(state: state).tabItem { Label("Reminders", systemImage: "checklist") }
            PhotosTab(state: state).tabItem { Label("Photos", systemImage: "photo.on.rectangle") }
            NotesTab(state: state).tabItem { Label("Notes", systemImage: "note.text") }
        }
        .padding()
        .frame(minWidth: 560, minHeight: 480)
    }
}

private struct ConnectionTab: View {
    @ObservedObject var state: AppState
    var body: some View {
        Form {
            Section {
                TextField("URL", text: $state.haURL, prompt: Text("http://homeassistant.local:8123"))
                SecureField("Long-lived access token", text: $state.token)
                HStack {
                    Button("Test Connection") { Task { await state.testConnection() } }
                    if let s = state.connectionStatus { Text(s).foregroundStyle(.secondary).lineLimit(2) }
                }
            } footer: {
                Text("Create a token in Home Assistant under your profile → Security → Long-lived access tokens (admin user). Install the mac_sync integration first.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section {
                Picker("Sync every", selection: $state.intervalMinutes) {
                    ForEach([5, 15, 30, 60, 180], id: \.self) { Text("\($0) min").tag($0) }
                }
                Toggle("Launch at login", isOn: Binding(get: { state.launchAtLogin }, set: { state.launchAtLogin = $0 }))
                Button(state.isSyncing ? "Syncing…" : "Sync Now") { Task { await state.syncNow() } }
                    .disabled(state.isSyncing)
            }
        }
        .formStyle(.grouped)
    }
}

private struct CalendarTab: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading) {
            if !state.eventKit.calendarAuthorized {
                PermissionPrompt(text: "HA Sync needs access to Calendar.") { await state.requestCalendar() }
            }
            HStack {
                Stepper("Past days: \(state.daysBack)", value: $state.daysBack, in: 0...365)
                Stepper("Future days: \(state.daysAhead)", value: $state.daysAhead, in: 1...730)
            }
            SelectionList(items: state.calendarCatalog, selection: $state.calendarIDs)
        }
    }
}

private struct RemindersTab: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading) {
            if !state.eventKit.remindersAuthorized {
                PermissionPrompt(text: "HA Sync needs access to Reminders.") { await state.requestReminders() }
            }
            Toggle("Include reminders completed in the last \(state.daysBack) days", isOn: $state.includeCompleted)
            SelectionList(items: state.reminderCatalog, selection: $state.reminderListIDs)
        }
    }
}

private struct PhotosTab: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading) {
            if !state.photos.authorized {
                PermissionPrompt(text: "HA Sync needs access to Photos.") { await state.requestPhotos() }
            }
            HStack {
                Picker("Newest photos per album", selection: $state.maxPhotosPerAlbum) {
                    ForEach([50, 100, 300, 1000, 5000], id: \.self) { Text("\($0)").tag($0) }
                }
                Picker("Max size", selection: $state.maxPixel) {
                    ForEach([1280, 1920, 2048, 3072, 4096], id: \.self) { Text("\($0) px").tag($0) }
                }
                Button("Refresh") { state.refreshLocalCatalogs() }
            }
            Text("Photos are saved to /media/mac_sync/<album> on Home Assistant. Videos are skipped.")
                .font(.caption).foregroundStyle(.secondary)
            SelectionList(items: state.albumCatalog, selection: $state.albumIDs)
        }
    }
}

private struct NotesTab: View {
    @ObservedObject var state: AppState
    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Button(state.notesLoading ? "Loading…" : "Load Folders from Notes") { Task { await state.loadNoteFolders() } }
                    .disabled(state.notesLoading)
                Stepper("Max characters per note: \(state.noteBodyLimit)", value: $state.noteBodyLimit, in: 200...20000, step: 200)
            }
            if let e = state.notesError { Text(e).foregroundStyle(.red).font(.caption) }
            Text("Locked notes are sent without their body.").font(.caption).foregroundStyle(.secondary)
            SelectionList(items: state.noteCatalog, selection: $state.noteFolderIDs)
        }
    }
}

private struct PermissionPrompt: View {
    let text: String
    let action: () async -> Void
    var body: some View {
        HStack {
            Image(systemName: "lock.fill").foregroundStyle(.orange)
            Text(text)
            Spacer()
            Button("Grant Access") { Task { await action() } }
        }
        .padding(8)
        .background(.orange.opacity(0.1), in: RoundedRectangle(cornerRadius: 6))
    }
}

struct SelectionList: View {
    let items: [CatalogItem]
    @Binding var selection: Set<String>

    private var groups: [(String, [CatalogItem])] {
        var order: [String] = []
        var map: [String: [CatalogItem]] = [:]
        for i in items {
            if map[i.group] == nil { order.append(i.group) }
            map[i.group, default: []].append(i)
        }
        return order.map { ($0, map[$0]!) }
    }

    var body: some View {
        if items.isEmpty {
            Text("Nothing to show yet.").foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            List {
                ForEach(groups, id: \.0) { group, rows in
                    Section(group) {
                        ForEach(rows) { item in
                            Toggle(isOn: Binding(
                                get: { selection.contains(item.id) },
                                set: { on in if on { selection.insert(item.id) } else { selection.remove(item.id) } }
                            )) {
                                HStack {
                                    Text(item.title)
                                    Spacer()
                                    if let d = item.detail { Text(d).foregroundStyle(.secondary) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

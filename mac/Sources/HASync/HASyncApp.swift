import SwiftUI

@main
struct HASyncApp: App {
    @StateObject private var state = AppState.shared

    var body: some Scene {
        MenuBarExtra {
            MenuContent(state: state)
        } label: {
            Image(systemName: state.isSyncing ? "arrow.triangle.2.circlepath" : "house.and.flag")
        }

        Window("HA Sync Settings", id: "settings") {
            SettingsView(state: state)
        }
        .windowResizability(.contentSize)
    }
}

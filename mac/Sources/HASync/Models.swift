import Foundation

/// Something the user can pick in Settings (a calendar, list, album or folder).
struct CatalogItem: Identifiable, Hashable {
    let id: String
    let title: String
    let group: String
    var detail: String? = nil
}

// MARK: - Payload sent to Home Assistant (keys become snake_case)

struct SyncPayload: Encodable {
    var source: String
    var calendars: [CalendarPayload]?
    var reminders: [ReminderListPayload]?
    var notes: [NoteFolderPayload]?
    var albums: [AlbumPayload]?
}

struct CalendarPayload: Encodable {
    let id: String
    let title: String
    let account: String
    let color: String?
    var events: [EventPayload]
}

struct EventPayload: Encodable {
    let uid: String
    let title: String
    let start: String
    let end: String
    let allDay: Bool
    let location: String?
    let notes: String?
}

struct ReminderListPayload: Encodable {
    let id: String
    let title: String
    let account: String
    var items: [ReminderPayload]
}

struct ReminderPayload: Encodable {
    let uid: String
    let title: String
    let completed: Bool
    let due: String?
    let dueAllDay: Bool
    let notes: String?
}

struct NoteFolderPayload: Encodable {
    let id: String
    let title: String
    let account: String
    var notes: [NotePayload]
}

struct NotePayload: Codable {
    let id: String
    let title: String
    let body: String
    let modified: String?
}

struct AlbumPayload: Encodable {
    let id: String
    let title: String
    let slug: String
    let kind: String
    let count: Int
    let files: [String]
}

struct PushResponse: Decodable {
    let ok: Bool
    let missing: [String: [String]]?
}

enum ISO {
    static let dateTime: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static let day: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

/// Lowercase, dash-separated, filesystem-safe.
func slugify(_ s: String) -> String {
    let allowed = CharacterSet.alphanumerics
    let folded = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current).lowercased()
    var out = ""
    for scalar in folded.unicodeScalars {
        if allowed.contains(scalar) && scalar.isASCII { out.unicodeScalars.append(scalar) }
        else if !out.hasSuffix("-") { out.append("-") }
    }
    let trimmed = out.trimmingCharacters(in: CharacterSet(charactersIn: "-"))
    return trimmed.isEmpty ? "album" : String(trimmed.prefix(80))
}

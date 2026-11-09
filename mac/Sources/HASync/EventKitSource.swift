import AppKit
import EventKit

/// Reads macOS Calendar and Reminders through EventKit.
final class EventKitSource {
    let store = EKEventStore()

    var calendarAuthorized: Bool { EKEventStore.authorizationStatus(for: .event) == .fullAccess }
    var remindersAuthorized: Bool { EKEventStore.authorizationStatus(for: .reminder) == .fullAccess }

    func requestCalendarAccess() async -> Bool {
        (try? await store.requestFullAccessToEvents()) ?? false
    }

    func requestRemindersAccess() async -> Bool {
        (try? await store.requestFullAccessToReminders()) ?? false
    }

    func catalog(for type: EKEntityType) -> [CatalogItem] {
        store.calendars(for: type)
            .map { CatalogItem(id: $0.calendarIdentifier, title: $0.title, group: $0.source?.title ?? "Other") }
            .sorted { ($0.group, $0.title) < ($1.group, $1.title) }
    }

    func events(calendarIDs: Set<String>, daysBack: Int, daysAhead: Int) -> [CalendarPayload] {
        let cals = store.calendars(for: .event).filter { calendarIDs.contains($0.calendarIdentifier) }
        guard !cals.isEmpty else { return [] }
        let cal = Calendar.current
        let start = cal.date(byAdding: .day, value: -daysBack, to: cal.startOfDay(for: Date()))!
        let end = cal.date(byAdding: .day, value: daysAhead + 1, to: cal.startOfDay(for: Date()))!

        var byCal: [String: CalendarPayload] = [:]
        for c in cals {
            byCal[c.calendarIdentifier] = CalendarPayload(
                id: c.calendarIdentifier, title: c.title, account: c.source?.title ?? "",
                color: Self.hex(c.color), events: [])
        }
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: cals)
        for e in store.events(matching: predicate) {
            guard let calID = e.calendar?.calendarIdentifier, let s = e.startDate, let en = e.endDate else { continue }
            let uid = "\(e.calendarItemIdentifier)_\(Int(s.timeIntervalSince1970))"
            let payload = EventPayload(
                uid: uid,
                title: e.title ?? "",
                start: e.isAllDay ? ISO.day.string(from: s) : ISO.dateTime.string(from: s),
                // EventKit all-day end is the last instant of the final day; HA wants an exclusive end date.
                end: e.isAllDay ? ISO.day.string(from: cal.date(byAdding: .day, value: 1, to: cal.startOfDay(for: en))!)
                                : ISO.dateTime.string(from: en),
                allDay: e.isAllDay,
                location: e.location.flatMap { $0.isEmpty ? nil : $0 },
                notes: e.notes.flatMap { $0.isEmpty ? nil : String($0.prefix(2000)) })
            byCal[calID]?.events.append(payload)
        }
        return Array(byCal.values)
    }

    func reminders(listIDs: Set<String>, includeCompleted: Bool, completedDaysBack: Int) async -> [ReminderListPayload] {
        let lists = store.calendars(for: .reminder).filter { listIDs.contains($0.calendarIdentifier) }
        guard !lists.isEmpty else { return [] }

        var predicates = [store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: lists)]
        if includeCompleted {
            let since = Calendar.current.date(byAdding: .day, value: -completedDaysBack, to: Date())!
            predicates.append(store.predicateForCompletedReminders(withCompletionDateStarting: since, ending: Date(), calendars: lists))
        }

        var byList: [String: ReminderListPayload] = [:]
        for l in lists {
            byList[l.calendarIdentifier] = ReminderListPayload(
                id: l.calendarIdentifier, title: l.title, account: l.source?.title ?? "", items: [])
        }
        for predicate in predicates {
            let items: [(String, ReminderPayload)] = await withCheckedContinuation { cont in
                store.fetchReminders(matching: predicate) { reminders in
                    let mapped = (reminders ?? []).compactMap { r -> (String, ReminderPayload)? in
                        guard let listID = r.calendar?.calendarIdentifier else { return nil }
                        var due: String?
                        var allDay = false
                        if let comps = r.dueDateComponents, let date = Calendar.current.date(from: comps) {
                            allDay = comps.hour == nil
                            due = allDay ? ISO.day.string(from: date) : ISO.dateTime.string(from: date)
                        }
                        return (listID, ReminderPayload(
                            uid: r.calendarItemIdentifier, title: r.title ?? "", completed: r.isCompleted,
                            due: due, dueAllDay: allDay,
                            notes: r.notes.flatMap { $0.isEmpty ? nil : String($0.prefix(2000)) }))
                    }
                    cont.resume(returning: mapped)
                }
            }
            for (listID, item) in items { byList[listID]?.items.append(item) }
        }
        return Array(byList.values)
    }

    private static func hex(_ color: NSColor?) -> String? {
        guard let c = color?.usingColorSpace(.sRGB) else { return nil }
        return String(format: "#%02X%02X%02X",
                      Int(round(c.redComponent * 255)), Int(round(c.greenComponent * 255)), Int(round(c.blueComponent * 255)))
    }
}

import Foundation

/// Notes has no public framework, so this drives it with JavaScript for Automation via osascript.
/// The first run triggers macOS's "HA Sync wants to control Notes" prompt.
final class NotesSource {
    enum NotesError: LocalizedError {
        case script(String)
        var errorDescription: String? {
            switch self {
            case .script(let msg):
                if msg.contains("-1743") || msg.localizedCaseInsensitiveContains("not allowed") {
                    return "Notes access denied. Allow HA Sync under System Settings → Privacy & Security → Automation → Notes."
                }
                return "Notes: \(msg.trimmingCharacters(in: .whitespacesAndNewlines))"
            }
        }
    }

    private static let listScript = """
    function run(argv) {
      const Notes = Application('Notes');
      const out = []; const seen = {};
      function walk(account, f, prefix) {
        const id = f.id();
        if (seen[id]) return; seen[id] = true;
        const name = prefix ? prefix + ' / ' + f.name() : f.name();
        out.push({id: id, title: name, account: account, count: f.notes.length});
        f.folders().forEach(c => walk(account, c, name));
      }
      Notes.accounts().forEach(a => { const an = a.name(); a.folders().forEach(f => walk(an, f, '')); });
      return JSON.stringify(out);
    }
    """

    private static let fetchScript = """
    function run(argv) {
      const Notes = Application('Notes');
      const limit = parseInt(argv[0], 10);
      const out = {};
      argv.slice(1).forEach(fid => {
        let f;
        try { f = Notes.folders.byId(fid); f.name(); } catch (e) { return; }
        const ids = f.notes.id(), names = f.notes.name(), mods = f.notes.modificationDate();
        let bodies;
        try { bodies = f.notes.plaintext(); }
        catch (e) { bodies = ids.map((_, i) => { try { return f.notes[i].plaintext(); } catch (e2) { return ''; } }); }
        out[fid] = ids.map((id, i) => {
          let body = bodies[i] || '';
          const nl = body.indexOf('\\n');
          if (nl >= 0 && body.slice(0, nl).trim() === (names[i] || '').trim()) body = body.slice(nl + 1);
          body = body.trim();
          if (body.length > limit) body = body.slice(0, limit) + '…';
          return {id: id, title: names[i], body: body, modified: mods[i] ? mods[i].toISOString() : null};
        });
      });
      return JSON.stringify(out);
    }
    """

    private func run(_ script: String, _ args: [String]) async throws -> Data {
        try await Task.detached {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            p.arguments = ["-l", "JavaScript", "-e", script] + args
            let out = Pipe(), err = Pipe()
            p.standardOutput = out
            p.standardError = err
            try p.run()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            let errData = err.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            guard p.terminationStatus == 0 else {
                throw NotesError.script(String(data: errData, encoding: .utf8) ?? "exit \(p.terminationStatus)")
            }
            return data
        }.value
    }

    func catalog() async throws -> [CatalogItem] {
        struct Folder: Decodable { let id: String; let title: String; let account: String; let count: Int }
        let folders = try JSONDecoder().decode([Folder].self, from: try await run(Self.listScript, []))
        return folders.map { CatalogItem(id: $0.id, title: $0.title, group: $0.account, detail: "\($0.count) notes") }
    }

    func fetch(folders: [CatalogItem], bodyLimit: Int) async throws -> [NoteFolderPayload] {
        guard !folders.isEmpty else { return [] }
        let data = try await run(Self.fetchScript, [String(bodyLimit)] + folders.map(\.id))
        let notes = try JSONDecoder().decode([String: [NotePayload]].self, from: data)
        return folders.compactMap { f in
            guard let list = notes[f.id] else { return nil }
            return NoteFolderPayload(id: f.id, title: f.title, account: f.group, notes: list)
        }
    }
}

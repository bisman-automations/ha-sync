import Foundation

enum HAError: LocalizedError {
    case badURL
    case noToken
    case http(Int, String)
    case integrationMissing

    var errorDescription: String? {
        switch self {
        case .badURL: return "Home Assistant URL is not valid."
        case .noToken: return "Add a long-lived access token in Settings."
        case .http(let code, let body):
            if code == 401 { return "Home Assistant rejected the token (401). Use an admin user's long-lived token." }
            if code == 404 { return "Mac Sync endpoint not found (404). Install the mac_sync integration and restart Home Assistant." }
            return "Home Assistant returned \(code): \(body.prefix(200))"
        case .integrationMissing:
            return "The mac_sync integration is installed but not added. Add it under Settings → Devices & services."
        }
    }
}

struct HAClient {
    let base: URL
    let token: String
    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 60
        return URLSession(configuration: cfg)
    }()

    init(urlString: String, token: String) throws {
        var s = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        while s.hasSuffix("/") { s.removeLast() }
        guard let url = URL(string: s), url.scheme?.hasPrefix("http") == true else { throw HAError.badURL }
        guard !token.isEmpty else { throw HAError.noToken }
        base = url
        self.token = token
    }

    private func request(_ path: String, method: String = "GET") -> URLRequest {
        var r = URLRequest(url: base.appendingPathComponent(path))
        r.httpMethod = method
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return r
    }

    private func send(_ r: URLRequest) async throws -> Data {
        let (data, resp) = try await session.data(for: r)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            throw HAError.http(code, String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    /// Verifies the URL, token and that the integration is loaded.
    func check() async throws -> String {
        _ = try await send(request("api/"))
        let data = try await send(request("api/mac_sync/push"))
        struct Status: Decodable { let ok: Bool; let version: String }
        let status = try JSONDecoder().decode(Status.self, from: data)
        guard status.ok else { throw HAError.integrationMissing }
        return "Connected — Mac Sync integration v\(status.version)"
    }

    func push(_ payload: SyncPayload) async throws -> PushResponse {
        var r = request("api/mac_sync/push", method: "POST")
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let enc = JSONEncoder()
        enc.keyEncodingStrategy = .convertToSnakeCase
        r.httpBody = try enc.encode(payload)
        return try JSONDecoder().decode(PushResponse.self, from: try await send(r))
    }

    func uploadPhoto(album: String, filename: String, jpeg: Data) async throws {
        let boundary = "HASync-\(UUID().uuidString)"
        var body = Data()
        func field(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n".data(using: .utf8)!)
        }
        field("album", album)
        field("filename", filename)
        body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\nContent-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(jpeg)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        var r = request("api/mac_sync/photo", method: "POST")
        r.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        r.httpBody = body
        _ = try await send(r)
    }
}

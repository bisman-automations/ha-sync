import Foundation
import ImageIO
import Photos
import UniformTypeIdentifiers

/// Reads albums (including iCloud Shared Albums and smart albums) from Photos.
final class PhotosSource {
    var authorized: Bool {
        let s = PHPhotoLibrary.authorizationStatus(for: .readWrite)
        return s == .authorized || s == .limited
    }

    func requestAccess() async -> Bool {
        let s = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        return s == .authorized || s == .limited
    }

    private func imageOptions() -> PHFetchOptions {
        let o = PHFetchOptions()
        o.predicate = NSPredicate(format: "mediaType == %d", PHAssetMediaType.image.rawValue)
        o.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        return o
    }

    static func kind(of c: PHAssetCollection) -> String {
        if c.assetCollectionSubtype == .albumCloudShared { return "Shared Albums" }
        if c.assetCollectionType == .smartAlbum { return "Smart Albums" }
        return "My Albums"
    }

    func catalog() -> [CatalogItem] {
        var items: [CatalogItem] = []
        for type in [PHAssetCollectionType.album, .smartAlbum] {
            let result = PHAssetCollection.fetchAssetCollections(with: type, subtype: .any, options: nil)
            result.enumerateObjects { c, _, _ in
                let count = PHAsset.fetchAssets(in: c, options: self.imageOptions()).count
                if type == .smartAlbum && count == 0 { return }
                items.append(CatalogItem(id: c.localIdentifier, title: c.localizedTitle ?? "Untitled",
                                         group: Self.kind(of: c), detail: "\(count) photos"))
            }
        }
        let order = ["My Albums": 0, "Shared Albums": 1, "Smart Albums": 2]
        return items.sorted { (order[$0.group] ?? 9, $0.title) < (order[$1.group] ?? 9, $1.title) }
    }

    struct Album {
        let collection: PHAssetCollection
        let assets: [String: PHAsset]   // filename -> asset
        let files: [String]
        let total: Int
    }

    func album(id: String, limit: Int) -> Album? {
        guard let c = PHAssetCollection.fetchAssetCollections(withLocalIdentifiers: [id], options: nil).firstObject else { return nil }
        let result = PHAsset.fetchAssets(in: c, options: imageOptions())
        var assets: [String: PHAsset] = [:]
        var files: [String] = []
        let n = min(result.count, limit)
        for i in 0..<n {
            let a = result.object(at: i)
            let name = Self.filename(for: a)
            assets[name] = a
            files.append(name)
        }
        return Album(collection: c, assets: assets, files: files, total: result.count)
    }

    /// Stable per asset version: edits change the timestamp, so HA re-downloads them.
    static func filename(for a: PHAsset) -> String {
        let uuid = a.localIdentifier.split(separator: "/").first.map(String.init) ?? a.localIdentifier
        let stamp = Int((a.modificationDate ?? a.creationDate ?? .distantPast).timeIntervalSince1970)
        return "\(uuid)_\(stamp).jpg"
    }

    /// Full-quality original (downloaded from iCloud if needed), scaled to `maxPixel`, re-encoded as JPEG
    /// with metadata (including GPS) stripped.
    func jpeg(for asset: PHAsset, maxPixel: Int) async -> Data? {
        let opts = PHImageRequestOptions()
        opts.isNetworkAccessAllowed = true
        opts.deliveryMode = .highQualityFormat
        opts.version = .current
        let data: Data? = await withCheckedContinuation { cont in
            PHImageManager.default().requestImageDataAndOrientation(for: asset, options: opts) { data, _, _, _ in
                cont.resume(returning: data)
            }
        }
        guard let data, let src = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let thumb: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: maxPixel,
            kCGImageSourceCreateThumbnailWithTransform: true,
        ]
        guard let img = CGImageSourceCreateThumbnailAtIndex(src, 0, thumb as CFDictionary) else { return nil }
        let out = NSMutableData()
        guard let dest = CGImageDestinationCreateWithData(out, UTType.jpeg.identifier as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(dest, img, [kCGImageDestinationLossyCompressionQuality: 0.85] as CFDictionary)
        guard CGImageDestinationFinalize(dest) else { return nil }
        return out as Data
    }
}

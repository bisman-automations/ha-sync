// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "HASync",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "HASync", path: "Sources/HASync")
    ]
)

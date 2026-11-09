import AppKit
import CoreGraphics
import Foundation

let S: CGFloat = 1024
let out = CommandLine.arguments[1]
let cs = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CGContext(data: nil, width: Int(S), height: Int(S), bitsPerComponent: 8, bytesPerRow: 0,
                    space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
// Flip so y grows downward.
ctx.translateBy(x: 0, y: S); ctx.scaleBy(x: 1, y: -1)

func rgb(_ h: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((h >> 16) & 255) / 255, green: CGFloat((h >> 8) & 255) / 255, blue: CGFloat(h & 255) / 255, alpha: a)
}

// Background tile (macOS icon grid: 824pt body, centred) with soft drop shadow.
let tile = CGRect(x: 100, y: 100, width: 824, height: 824)
let tilePath = CGPath(roundedRect: tile, cornerWidth: 186, cornerHeight: 186, transform: nil)
ctx.saveGState()
ctx.setShadow(offset: CGSize(width: 0, height: 14), blur: 30, color: rgb(0x000000, 0.35))
ctx.addPath(tilePath); ctx.setFillColor(rgb(0x1F8FE5)); ctx.fillPath()
ctx.restoreGState()
ctx.saveGState()
ctx.addPath(tilePath); ctx.clip()
let bg = CGGradient(colorsSpace: cs, colors: [rgb(0x4FC8F7), rgb(0x1E7BE0), rgb(0x1452B8)] as CFArray, locations: [0, 0.6, 1])!
ctx.drawLinearGradient(bg, start: CGPoint(x: 300, y: 100), end: CGPoint(x: 724, y: 924), options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
// subtle top sheen
let sheen = CGGradient(colorsSpace: cs, colors: [rgb(0xFFFFFF, 0.18), rgb(0xFFFFFF, 0)] as CFArray, locations: [0, 1])!
ctx.drawLinearGradient(sheen, start: CGPoint(x: 512, y: 100), end: CGPoint(x: 512, y: 520), options: [])
ctx.restoreGState()

// House: white, rounded joins.
let house = CGMutablePath()
house.move(to: CGPoint(x: 512, y: 232))       // roof peak
house.addLine(to: CGPoint(x: 806, y: 478))    // right eave
house.addLine(to: CGPoint(x: 734, y: 478))
house.addLine(to: CGPoint(x: 734, y: 776))    // right wall bottom
house.addLine(to: CGPoint(x: 290, y: 776))
house.addLine(to: CGPoint(x: 290, y: 478))
house.addLine(to: CGPoint(x: 218, y: 478))    // left eave
house.closeSubpath()
ctx.saveGState()
ctx.setShadow(offset: CGSize(width: 0, height: 10), blur: 24, color: rgb(0x0A2A66, 0.35))
ctx.beginTransparencyLayer(auxiliaryInfo: nil)
ctx.addPath(house); ctx.setFillColor(rgb(0xFFFFFF))
ctx.setStrokeColor(rgb(0xFFFFFF)); ctx.setLineWidth(40); ctx.setLineJoin(.round)
ctx.drawPath(using: .fillStroke)
ctx.endTransparencyLayer()
ctx.restoreGState()

// Sync arrows inside the house, in the brand blue.
let c = CGPoint(x: 512, y: 600), r: CGFloat = 112, w: CGFloat = 38
ctx.setStrokeColor(rgb(0x1C74DC)); ctx.setFillColor(rgb(0x1C74DC))
ctx.setLineWidth(w); ctx.setLineCap(.round)
func deg(_ d: CGFloat) -> CGFloat { d * .pi / 180 }
for start in [CGFloat(200), 20] {                     // two arcs, 180° apart
    let end = start + 120
    ctx.addArc(center: c, radius: r, startAngle: deg(start), endAngle: deg(end), clockwise: false)
    ctx.strokePath()
    // Arrowhead at the arc end, pointing along the direction of travel.
    let a = deg(end)
    let tip = CGPoint(x: c.x + r * cos(a), y: c.y + r * sin(a))
    let tangent = CGPoint(x: -sin(a), y: cos(a))
    let normal = CGPoint(x: cos(a), y: sin(a))
    let len: CGFloat = 70, half: CGFloat = 50
    let point = CGPoint(x: tip.x + tangent.x * len * 0.75, y: tip.y + tangent.y * len * 0.75)
    let base = CGPoint(x: tip.x - tangent.x * len * 0.25, y: tip.y - tangent.y * len * 0.25)
    ctx.move(to: point)
    ctx.addLine(to: CGPoint(x: base.x + normal.x * half, y: base.y + normal.y * half))
    ctx.addLine(to: CGPoint(x: base.x - normal.x * half, y: base.y - normal.y * half))
    ctx.closePath(); ctx.fillPath()
}

let img = ctx.makeImage()!
let rep = NSBitmapImageRep(cgImage: img)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
print("wrote \(out)")

// app/make_icon.swift — 產生 1024x1024 App 圖示 PNG：swift make_icon.swift out.png
import AppKit

let size: CGFloat = 1024
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let rect = NSRect(x: 80, y: 80, width: size - 160, height: size - 160)
let path = NSBezierPath(roundedRect: rect, xRadius: 190, yRadius: 190)
NSGradient(colors: [NSColor(red: 0.45, green: 0.52, blue: 1.0, alpha: 1), NSColor(red: 0.30, green: 0.32, blue: 0.85, alpha: 1)])!
    .draw(in: path, angle: -90)
if let sym = NSImage(systemSymbolName: "bubble.left.and.bubble.right.fill", accessibilityDescription: nil)?
    .withSymbolConfiguration(.init(pointSize: 460, weight: .regular)) {
    let tinted = NSImage(size: sym.size, flipped: false) { r in
        sym.draw(in: r); NSColor.white.set(); r.fill(using: .sourceAtop); return true
    }
    tinted.draw(at: NSPoint(x: (size - tinted.size.width) / 2, y: (size - tinted.size.height) / 2),
                from: .zero, operation: .sourceOver, fraction: 1)
}
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))

// app/MemoryUsage.swift
// 一次性取樣：App 本體加上它底下所有子行程（Python、瀏覽器…）目前的實體記憶體（RSS）。
import Foundation

struct MemoryUsage {
    var appMB: Double
    var childrenMB: Double
    var childCount: Int
    var totalMB: Double { appMB + childrenMB }

    static func snapshot() -> MemoryUsage? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/ps")
        p.arguments = ["-axo", "pid=,ppid=,rss="]
        let out = Pipe(); p.standardOutput = out; p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return nil }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()

        var rss: [Int32: Double] = [:], children: [Int32: [Int32]] = [:]
        for line in String(decoding: data, as: UTF8.self).split(separator: "\n") {
            let f = line.split(separator: " ")
            guard f.count == 3, let pid = Int32(f[0]), let ppid = Int32(f[1]), let kb = Double(f[2]) else { continue }
            rss[pid] = kb / 1024; children[ppid, default: []].append(pid)
        }
        let me = ProcessInfo.processInfo.processIdentifier
        var stack = children[me] ?? [], desc: [Int32] = []
        while let pid = stack.popLast() { desc.append(pid); stack += children[pid] ?? [] }
        return MemoryUsage(appMB: rss[me] ?? 0,
                           childrenMB: desc.reduce(0) { $0 + (rss[$1] ?? 0) },
                           childCount: desc.count)
    }

    var summary: String { String(format: "合計 %.0f MB", totalMB) }
    var detail: String { String(format: "App %.0f MB ＋ %d 個子行程 %.0f MB", appMB, childCount, childrenMB) }
}

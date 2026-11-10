// app/MemoryUsage.swift
// 一次性取樣：App 本體加上它底下所有子行程（Python、瀏覽器…）目前的記憶體用量。
// 用 phys_footprint（與活動監視器「記憶體」欄位相同），不用 RSS——RSS 會把與系統共用的框架也算進去而偏大。
import Foundation

struct MemoryUsage {
    var appMB: Double
    var childrenMB: Double
    var childCount: Int
    var totalMB: Double { appMB + childrenMB }

    static func snapshot() -> MemoryUsage? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/ps")
        p.arguments = ["-axo", "pid=,ppid="]
        let out = Pipe(); p.standardOutput = out; p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return nil }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()

        var children: [Int32: [Int32]] = [:]
        for line in String(decoding: data, as: UTF8.self).split(separator: "\n") {
            let f = line.split(separator: " ")
            guard f.count == 2, let pid = Int32(f[0]), let ppid = Int32(f[1]) else { continue }
            children[ppid, default: []].append(pid)
        }
        func footprintMB(_ pid: Int32) -> Double {
            var info = rusage_info_v4()
            let r = withUnsafeMutablePointer(to: &info) {
                $0.withMemoryRebound(to: rusage_info_t?.self, capacity: 1) { proc_pid_rusage(pid, RUSAGE_INFO_V4, $0) }
            }
            return r == 0 ? Double(info.ri_phys_footprint) / 1_048_576 : 0
        }
        let me = ProcessInfo.processInfo.processIdentifier
        var stack = children[me] ?? [], desc: [Int32] = []
        while let pid = stack.popLast() { desc.append(pid); stack += children[pid] ?? [] }
        return MemoryUsage(appMB: footprintMB(me),
                           childrenMB: desc.reduce(0) { $0 + footprintMB($1) },
                           childCount: desc.count)
    }

    var summary: String { String(format: "合計 %.0f MB", totalMB) }
    var detail: String { String(format: "App %.0f MB ＋ %d 個子行程 %.0f MB", appMB, childCount, childrenMB) }
}

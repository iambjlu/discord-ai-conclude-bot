// app/BotRunner.swift
// 管理一個 Python 腳本子行程：啟動、停止、（常駐型）當掉自動重啟，並收集日誌。
import Foundation

@MainActor
final class BotRunner: ObservableObject, Identifiable {
    enum State: Equatable {
        case stopped
        case running
        case backoff(Int)          // 幾秒後重啟
        case finished(Int32)       // 一次性腳本跑完（exit code）
    }

    let id: String
    let title: String
    let script: String
    let keepAlive: Bool            // true＝常駐（當掉自動重啟）；false＝一次性
    let maxRuntime: TimeInterval?  // 一次性腳本的逾時上限

    @Published private(set) var state: State = .stopped
    @Published private(set) var logs: [String] = []
    @Published private(set) var lastStart: Date?

    private var process: Process?
    private var wantRunning = false
    private var failures = 0
    private var outBuf = Data()
    private var retryTask: Task<Void, Never>?
    private var timeoutTask: Task<Void, Never>?
    private var envProvider: () -> [String: String] = { [:] }
    private let maxLines = 1000
    private let logFile: URL

    init(id: String, title: String, script: String, keepAlive: Bool, maxRuntime: TimeInterval? = nil) {
        self.id = id; self.title = title; self.script = script
        self.keepAlive = keepAlive; self.maxRuntime = maxRuntime
        let dir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/DiscordAIConcludeBot")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        logFile = dir.appendingPathComponent("\(id).log")
    }

    var isRunning: Bool { process?.isRunning ?? false }

    func start(env: @escaping () -> [String: String]) {
        envProvider = env
        wantRunning = true
        launch()
    }

    func stop() {
        wantRunning = false
        retryTask?.cancel(); timeoutTask?.cancel()
        process?.terminate()
        if process == nil { state = .stopped }
    }

    func restart(env: @escaping () -> [String: String]) {
        stop()
        Task { @MainActor in
            for _ in 0..<40 where self.isRunning { try? await Task.sleep(nanoseconds: 100_000_000) }
            self.start(env: env)
        }
    }

    /// App 結束時用：送 SIGTERM 並最多等 3 秒，逾時強殺
    func terminateAndWait() {
        wantRunning = false
        guard let p = process, p.isRunning else { return }
        p.terminate()
        let deadline = Date().addingTimeInterval(3)
        while p.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    func clearLogs() { logs.removeAll() }

    // MARK: - 內部

    private func launch() {
        guard process == nil else { return }
        guard let core = Bundle.main.resourceURL?.appendingPathComponent("core/run.sh"),
              FileManager.default.isExecutableFile(atPath: core.path) else {
            append("❌ 找不到內建的 core/run.sh（請用 build_app.sh 打包）")
            state = .stopped; return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [core.path, script]
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        env.merge(envProvider()) { _, new in new }
        p.environment = env
        let out = Pipe()
        p.standardOutput = out; p.standardError = out
        p.standardInput = FileHandle.nullDevice
        out.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            if d.isEmpty { h.readabilityHandler = nil; return }
            let me = self
            Task { @MainActor in me?.ingest(d) }
        }
        p.terminationHandler = { [weak self] proc in
            let me = self, code = proc.terminationStatus
            Task { @MainActor in me?.exited(code) }
        }
        do {
            try p.run()
        } catch {
            append("❌ 啟動失敗：\(error.localizedDescription)")
            state = .stopped; return
        }
        process = p
        lastStart = Date()
        state = .running
        append("▶️ 啟動 \(script)（pid \(p.processIdentifier)）")
        if let limit = maxRuntime {
            timeoutTask = Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: UInt64(limit * 1_000_000_000))
                guard let self, !Task.isCancelled, self.isRunning else { return }
                self.append("⏱️ 超過 \(Int(limit / 60)) 分鐘，強制結束")
                self.process?.terminate()
            }
        }
    }

    private func exited(_ code: Int32) {
        timeoutTask?.cancel()
        let ranFor = Date().timeIntervalSince(lastStart ?? Date())
        process = nil
        if !outBuf.isEmpty { flushLine(outBuf); outBuf.removeAll() }
        append("⏹️ 結束（exit \(code)）")
        guard wantRunning else { state = keepAlive ? .stopped : .finished(code); return }
        guard keepAlive else { state = .finished(code); wantRunning = false; return }
        failures = ranFor > 60 ? 0 : failures + 1
        let delay = min(60, 1 << min(failures, 6))
        state = .backoff(delay)
        append("🔁 \(delay) 秒後自動重啟")
        retryTask = Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(delay) * 1_000_000_000)
            guard let self, !Task.isCancelled, self.wantRunning else { return }
            self.launch()
        }
    }

    private func ingest(_ data: Data) {
        outBuf.append(data)
        while let nl = outBuf.firstIndex(of: 0x0A) {
            flushLine(outBuf[outBuf.startIndex..<nl])
            outBuf.removeSubrange(outBuf.startIndex...nl)
        }
    }

    private func flushLine(_ d: Data) {
        let s = String(decoding: d, as: UTF8.self).trimmingCharacters(in: .controlCharacters.subtracting(.init(charactersIn: "\t")))
        if !s.isEmpty { append(s) }
    }

    private func append(_ line: String) {
        logs.append(line)
        if logs.count > maxLines { logs.removeFirst(logs.count - maxLines) }
        writeToFile(line)
    }

    private func writeToFile(_ line: String) {
        let fm = FileManager.default
        if let size = (try? fm.attributesOfItem(atPath: logFile.path))?[.size] as? Int, size > 5_000_000 {
            let old = logFile.deletingPathExtension().appendingPathExtension("1.log")
            try? fm.removeItem(at: old); try? fm.moveItem(at: logFile, to: old)
        }
        if !fm.fileExists(atPath: logFile.path) { fm.createFile(atPath: logFile.path, contents: nil) }
        if let h = try? FileHandle(forWritingTo: logFile) {
            _ = try? h.seekToEnd()
            try? h.write(contentsOf: Data("\(ISO8601DateFormatter().string(from: Date())) \(line)\n".utf8))
            try? h.close()
        }
    }
}

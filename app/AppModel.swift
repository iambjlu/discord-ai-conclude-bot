// app/AppModel.swift
// 兩個 bot 的總管：常駐的 tagged_reply.py ＋ 定時執行的 server.py，以及 .env 與排程設定。
import AppKit
import Foundation
import ServiceManagement

@MainActor
final class AppModel: ObservableObject {
    static let forceFlags: [(env: String, title: String)] = [
        ("FORCE_AI_SUMMARY", "AI 總結"),
        ("FORCE_DAILY_QUOTE", "每日金句"),
        ("FORCE_DAILY_AI_SUMMARY", "每日摘要彙整"),
        ("FORCE_LINK_SCREENSHOT", "連結截圖"),
        ("FORCE_WEATHER_FORECAST", "天氣預報"),
    ]

    let tagged = BotRunner(id: "tagged_reply", title: "標注回覆", script: "tagged_reply.py", keepAlive: true)
    let server = BotRunner(id: "server", title: "排程任務", script: "server.py", keepAlive: false, maxRuntime: 45 * 60)

    // 偏好（每台電腦各自，存 UserDefaults）
    @Published var scheduleEnabled: Bool { didSet { UserDefaults.standard.set(scheduleEnabled, forKey: "scheduleEnabled") } }
    @Published var intervalHours: Int { didSet { UserDefaults.standard.set(intervalHours, forKey: "intervalHours") } }
    @Published var minuteOffset: Int { didSet { UserDefaults.standard.set(minuteOffset, forKey: "minuteOffset") } }
    @Published var autoStartTagged: Bool { didSet { UserDefaults.standard.set(autoStartTagged, forKey: "autoStartTagged") } }
    @Published var showWindowOnLaunch: Bool { didSet { UserDefaults.standard.set(showWindowOnLaunch, forKey: "showWindowOnLaunch") } }
    @Published var loginItem: Bool = SMAppService.mainApp.status == .enabled
    @Published var loginItemError: String?

    // .env
    @Published var envText: String = ""
    @Published var envAvailability: EnvStore.Availability = .missing
    @Published var envMessage: String = ""

    @Published var lastServerRun: Date? = UserDefaults.standard.object(forKey: "lastServerRun") as? Date
    private var lastSlot: String = UserDefaults.standard.string(forKey: "lastSlot") ?? ""
    private var timer: Timer?

    init() {
        let d = UserDefaults.standard
        scheduleEnabled = d.object(forKey: "scheduleEnabled") as? Bool ?? true
        intervalHours = d.object(forKey: "intervalHours") as? Int ?? 2
        minuteOffset = d.object(forKey: "minuteOffset") as? Int ?? 3
        autoStartTagged = d.object(forKey: "autoStartTagged") as? Bool ?? true
        showWindowOnLaunch = d.object(forKey: "showWindowOnLaunch") as? Bool ?? true
        AppModel.current = self
        // 啟動時視為「這一輪已處理」，避免一開 App 就自動跑排程（會發總結打擾別人）
        if let slot = currentSlot(Date()) { lastSlot = slot.id }
        refreshEnv()
        startTimer()
    }

    private func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            MainActor.assumeIsolated { AppModel.current?.tick() }
        }
        tick()
    }

    // MARK: - .env

    func refreshEnv() {
        envAvailability = EnvStore.availability()
        switch envAvailability {
        case .ready:
            envText = EnvStore.read() ?? ""
            envMessage = ""
        case .downloading: envMessage = "正在從 iCloud 下載設定檔…"
        case .missing: envMessage = "iCloud 上還沒有設定檔，請在「設定檔」頁建立"
        }
    }

    /// 存檔後如果有在跑就重新啟動，讓新設定生效
    func saveEnv() {
        do {
            try EnvStore.write(envText)
            envAvailability = .ready
            envMessage = "已儲存到 iCloud Drive"
            if tagged.isRunning { restartTagged() }
        } catch {
            envMessage = "儲存失敗：\(error.localizedDescription)"
        }
    }

    private func botEnv(extra: [String: String] = [:]) -> [String: String] {
        var e = extra
        e["BOT_ENV_FILE"] = EnvStore.file.path
        return e
    }

    // MARK: - 控制

    func startTagged() {
        refreshEnv()
        guard envAvailability == .ready else { return }
        tagged.start { self.botEnv() }
    }
    func stopTagged() { tagged.stop() }
    func restartTagged() { refreshEnv(); tagged.restart { self.botEnv() } }

    /// force 為要強制執行的 FORCE_* 環境變數名稱
    func runServer(force: [String] = []) {
        refreshEnv()
        guard envAvailability == .ready, !server.isRunning else { return }
        var extra: [String: String] = [:]
        for f in force { extra[f] = "true" }
        server.start { self.botEnv(extra: extra) }
        lastServerRun = Date()
        UserDefaults.standard.set(lastServerRun, forKey: "lastServerRun")
    }

    /// 手動執行排程任務前，連續確認兩次（預設按鈕都是「取消」）
    func requestRunServer(force: [String] = []) {
        guard !server.isRunning else { return }
        let names = force.isEmpty ? "依排程判斷的項目"
            : AppModel.forceFlags.filter { force.contains($0.env) }.map(\.title).joined(separator: "、")
        guard confirm("要立即執行排程任務嗎？", "將執行：\(names)。\n可能會在 Discord 頻道發送總結／圖片，打擾到其他人。", ok: "繼續") else { return }
        guard confirm("再確認一次", "真的要現在就送出嗎？（\(names)）", ok: "確定執行", destructive: true) else { return }
        runServer(force: force)
    }

    private func confirm(_ title: String, _ text: String, ok: String, destructive: Bool = false) -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert()
        a.messageText = title; a.informativeText = text
        a.alertStyle = destructive ? .critical : .warning
        a.addButton(withTitle: "取消")      // 第一顆＝預設（Return）
        a.addButton(withTitle: ok)
        return a.runModal() == .alertSecondButtonReturn
    }

    func stopServer() { server.stop() }

    func shutdown() {
        timer?.invalidate()
        tagged.terminateAndWait()
        server.terminateAndWait()
    }

    func setLoginItem(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            loginItemError = nil
        } catch {
            loginItemError = "設定開機啟動失敗：\(error.localizedDescription)（App 需放在「應用程式」資料夾）"
        }
        loginItem = SMAppService.mainApp.status == .enabled
    }

    // MARK: - 排程

    /// 目前這一輪排程的時間點：小時為 intervalHours 的倍數、分鐘為 minuteOffset
    private func currentSlot(_ now: Date) -> (id: String, time: Date)? {
        let cal = Calendar.current
        var c = cal.dateComponents([.year, .month, .day, .hour], from: now)
        c.hour = (c.hour! / intervalHours) * intervalHours
        c.minute = minuteOffset; c.second = 0
        guard let t = cal.date(from: c) else { return nil }
        return ("\(c.year!)-\(c.month!)-\(c.day!)-\(c.hour!)", t)
    }

    var nextRun: Date? {
        guard scheduleEnabled, let slot = currentSlot(Date()) else { return nil }
        let now = Date()
        if slot.time > now { return slot.time }
        return Calendar.current.date(byAdding: .hour, value: intervalHours, to: slot.time)
    }

    func tick() {
        if autoStartTagged, envAvailability != .ready { refreshEnv() }
        if autoStartTagged, tagged.state == .stopped, !userStoppedTagged, envAvailability == .ready { startTagged() }
        guard scheduleEnabled, !server.isRunning, let slot = currentSlot(Date()) else { return }
        guard slot.id != lastSlot, Date() >= slot.time else { return }
        lastSlot = slot.id
        UserDefaults.standard.set(lastSlot, forKey: "lastSlot")
        // 睡眠醒來後最多補跑 90 分鐘內錯過的那一輪；更久以前的就略過
        if Date().timeIntervalSince(slot.time) < 90 * 60 { runServer() }
    }

    /// 使用者在 UI 手動停止後，不要被 tick 自動拉起來
    private(set) var userStoppedTagged = false
    func userStartTagged() { userStoppedTagged = false; startTagged() }
    func userStopTagged() { userStoppedTagged = true; stopTagged() }
}

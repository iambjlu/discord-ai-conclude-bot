// app/Permissions.swift
// 第一次開啟（或重新打包、簽章身分改變後第一次開啟）時，把會用到的系統權限一次要過一遍。
// 臨時簽章（ad-hoc）每次打包身分都會變，macOS 會把先前同意過的權限視為另一個 App 而重新詢問，
// 所以用「執行檔指紋」判斷是否換了版本，換了就主動再要一次，而不是等到 bot 連線失敗才發現。
import AppKit
import Foundation
import Network

enum Permissions {
    private static let fingerprintKey = "permissionsFingerprint"

    /// 執行檔的大小＋修改時間；重新打包就會不同
    private static var fingerprint: String {
        guard let url = Bundle.main.executableURL,
              let a = try? FileManager.default.attributesOfItem(atPath: url.path) else { return "unknown" }
        let size = (a[.size] as? Int) ?? 0
        let mtime = (a[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
        return "\(size)-\(Int(mtime))"
    }

    /// 第一次或換版本才會真的要；force 為使用者手動按「重新要求權限」
    @MainActor
    static func requestIfNeeded(force: Bool = false, localAIEndpoint: URL?) {
        let d = UserDefaults.standard
        guard force || d.string(forKey: fingerprintKey) != fingerprint else { return }
        d.set(fingerprint, forKey: fingerprintKey)
        NSApp.activate(ignoringOtherApps: true)
        requestICloudDrive()
        requestLocalNetwork(endpoint: localAIEndpoint)
    }

    /// iCloud Drive（bot.env 所在）：實際讀一次資料夾，觸發檔案存取權限
    private static func requestICloudDrive() {
        _ = try? FileManager.default.contentsOfDirectory(at: EnvStore.folder, includingPropertiesForKeys: nil)
        _ = EnvStore.availability()
    }

    /// 區域網路：Bonjour 瀏覽是觸發權限對話框的標準做法；有設定本機 AI 位址時再實際連一次該位址。
    /// （Python 子行程的區網連線會算在這個 App 頭上，所以只要 App 取得權限，bot 就能連到區網的 AI 服務。）
    private static func requestLocalNetwork(endpoint: URL?) {
        let browser = NWBrowser(for: .bonjour(type: "_http._tcp", domain: nil), using: NWParameters())
        browser.stateUpdateHandler = { _ in }
        browser.browseResultsChangedHandler = { _, _ in }
        browser.start(queue: .global())

        var conn: NWConnection?
        if let ep = endpoint, let host = ep.host,
           let port = NWEndpoint.Port(rawValue: UInt16(ep.port ?? (ep.scheme == "https" ? 443 : 80))) {
            conn = NWConnection(host: NWEndpoint.Host(host), port: port, using: .tcp)
            conn?.start(queue: .global())
        }
        // 對話框出現後給使用者一點時間；之後收掉
        DispatchQueue.global().asyncAfter(deadline: .now() + 60) {
            browser.cancel(); conn?.cancel()
        }
    }

    static func openLocalNetworkSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_LocalNetwork") {
            NSWorkspace.shared.open(url)
        }
    }
}

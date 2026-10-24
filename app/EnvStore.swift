// app/EnvStore.swift
// 設定檔（bot.env）放在 iCloud Drive，換電腦登入 iCloud 後 App 直接讀得到。
// 注意：檔名不能以「.」開頭，iCloud Drive 不會同步 dotfile，所以不叫 .env。
import Foundation

enum EnvStore {
    static let folderName = "DiscordAIConcludeBot"
    static let fileName = "bot.env"

    static var folder: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs/\(folderName)")
    }
    static var file: URL { folder.appendingPathComponent(fileName) }
    private static var placeholder: URL { folder.appendingPathComponent(".\(fileName).icloud") }

    enum Availability { case ready, downloading, missing }

    /// 檔案可用嗎？若只剩 iCloud 佔位檔（尚未下載）就要求下載。
    static func availability() -> Availability {
        let fm = FileManager.default
        if fm.fileExists(atPath: file.path) { return .ready }
        if fm.fileExists(atPath: placeholder.path) {
            try? fm.startDownloadingUbiquitousItem(at: file)
            return .downloading
        }
        return .missing
    }

    static func read() -> String? { try? String(contentsOf: file, encoding: .utf8) }

    static func write(_ text: String) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try text.write(to: file, atomically: true, encoding: .utf8)
    }

    static let template = """
    DISCORD_BOT_TOKEN=
    GEMINI_API_KEY=

    SOURCE_CHANNEL_IDS=
    TARGET_CHANNEL_ID=
    TARGET_PREVIEW_ID=
    TARGET_WEATHER_ID=
    HELLO_MSG_ID=
    WEATHER_KEY=

    LOCAL_AI_SERVER=
    LOCAL_AI_MODEL=
    LOCAL_AI_API_KEY=
    LOCAL_AI_IMAGE_SUPPORT=true
    """
}

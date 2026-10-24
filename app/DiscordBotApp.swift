// app/DiscordBotApp.swift
// Discord AI Conclude Bot 選單列 App（同時保留 Dock 圖示）。
import AppKit
import SwiftUI

@main
struct DiscordBotApp: App {
    @StateObject private var model = AppModel()

    init() {
        signal(SIGPIPE, SIG_IGN)
        NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification,
                                               object: nil, queue: .main) { _ in
            // 由 Timer/Task 裡的 model 不方便取得，所以走全域參考
            MainActor.assumeIsolated { AppModel.current?.shutdown() }
        }
    }

    var body: some Scene {
        MenuBarExtra {
            MenuContent(model: model)
        } label: {
            MenuIcon(model: model)
        }
        .menuBarExtraStyle(.window)

        Window("Discord AI Bot", id: "main") {
            MainWindow(model: model)
                .frame(minWidth: 680, minHeight: 480)
                // 平常只在選單列（accessory）；主視窗開著時才出現在 Dock，關掉就消失
                .onAppear {
                    NSApp.setActivationPolicy(.regular)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .onDisappear { NSApp.setActivationPolicy(.accessory) }
        }
        .defaultSize(width: 820, height: 600)
    }
}

extension AppModel {
    static weak var current: AppModel?
}

/// 選單列圖示；App 一啟動就會建立，順便在這裡依設定開主視窗（只做一次）並註冊全域參考。
struct MenuIcon: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var tagged: BotRunner
    @ObservedObject private var server: BotRunner
    @Environment(\.openWindow) private var openWindow
    @State private var handled = false

    init(model: AppModel) {
        self.model = model
        _tagged = ObservedObject(wrappedValue: model.tagged)
        _server = ObservedObject(wrappedValue: model.server)
    }

    var body: some View {
        Image(systemName: symbol)
            .task {
                guard !handled else { return }
                handled = true
                AppModel.current = model
                if model.autoStartTagged { model.userStartTagged() }
                if model.showWindowOnLaunch {
                    openWindow(id: "main")
                    NSApp.activate(ignoringOtherApps: true)
                }
            }
    }

    private var symbol: String {
        if server.isRunning { return "arrow.triangle.2.circlepath" }
        switch tagged.state {
        case .running: return "bubble.left.and.bubble.right.fill"
        case .backoff: return "exclamationmark.bubble"
        default: return "bubble.left.and.bubble.right"
        }
    }
}

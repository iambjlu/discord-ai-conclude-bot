// app/Views.swift
import AppKit
import SwiftUI

private func describe(_ s: BotRunner.State) -> (text: String, color: Color) {
    switch s {
    case .stopped: return ("已停止", .secondary)
    case .running: return ("運行中", .green)
    case .backoff(let n): return ("\(n) 秒後重啟", .orange)
    case .finished(let c): return (c == 0 ? "上次執行完成" : "上次異常結束（\(c)）", c == 0 ? .secondary : .red)
    }
}

private let timeFmt: DateFormatter = {
    let f = DateFormatter(); f.dateFormat = "M/d HH:mm"; return f
}()

// MARK: - 選單列

struct MenuContent: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var tagged: BotRunner
    @ObservedObject private var server: BotRunner
    @Environment(\.openWindow) private var openWindow

    init(model: AppModel) {
        self.model = model
        _tagged = ObservedObject(wrappedValue: model.tagged)
        _server = ObservedObject(wrappedValue: model.server)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            row(tagged.title, describe(tagged.state))
            row(server.title, describe(server.state))
            if let next = model.nextRun { Text("下次排程：\(timeFmt.string(from: next))").font(.caption).foregroundStyle(.secondary) }
            if model.envAvailability != .ready { Text(model.envMessage).font(.caption).foregroundStyle(.orange) }
            Divider()
            if tagged.isRunning {
                Button("重新啟動標注回覆") { model.restartTagged() }
                Button("停止標注回覆") { model.userStopTagged() }
            } else {
                Button("啟動標注回覆") { model.userStartTagged() }
            }
            Button(server.isRunning ? "排程任務執行中…" : "立即執行排程任務") { model.requestRunServer() }
                .disabled(server.isRunning)
            Divider()
            Button("開啟主視窗") {
                openWindow(id: "main"); NSApp.activate(ignoringOtherApps: true)
            }
            Button("結束") { NSApp.terminate(nil) }
        }
        .buttonStyle(.plain)
        .padding(14)
        .frame(width: 250, alignment: .leading)
    }

    private func row(_ name: String, _ d: (text: String, color: Color)) -> some View {
        HStack { Circle().fill(d.color).frame(width: 8, height: 8); Text(name); Spacer(); Text(d.text).foregroundStyle(.secondary).font(.caption) }
    }
}

// MARK: - 主視窗

struct MainWindow: View {
    @ObservedObject var model: AppModel

    var body: some View {
        TabView {
            StatusTab(model: model).tabItem { Label("狀態", systemImage: "gauge") }
            LogTab(model: model).tabItem { Label("日誌", systemImage: "text.alignleft") }
            EnvTab(model: model).tabItem { Label("設定檔", systemImage: "key.icloud") }
        }
        .padding()
    }
}

struct StatusTab: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var tagged: BotRunner
    @ObservedObject private var server: BotRunner

    init(model: AppModel) {
        self.model = model
        _tagged = ObservedObject(wrappedValue: model.tagged)
        _server = ObservedObject(wrappedValue: model.server)
    }

    var body: some View {
        Form {
            Section("標注回覆（tagged_reply.py，常駐）") {
                LabeledContent("狀態") { let d = describe(tagged.state); Text(d.text).foregroundStyle(d.color) }
                HStack {
                    if tagged.isRunning {
                        Button("重新啟動") { model.restartTagged() }
                        Button("停止") { model.userStopTagged() }
                    } else {
                        Button("啟動") { model.userStartTagged() }
                    }
                }
                Toggle("App 開啟時自動啟動", isOn: $model.autoStartTagged)
            }
            Section("排程任務（server.py，定時執行後自動結束）") {
                LabeledContent("狀態") { let d = describe(server.state); Text(d.text).foregroundStyle(d.color) }
                Toggle("啟用定時排程", isOn: $model.scheduleEnabled)
                Stepper("每 \(model.intervalHours) 小時一次", value: $model.intervalHours, in: 1...24)
                Stepper("於整點後第 \(model.minuteOffset) 分鐘", value: $model.minuteOffset, in: 0...59)
                if let n = model.nextRun { LabeledContent("下次排程", value: timeFmt.string(from: n)) }
                if let l = model.lastServerRun { LabeledContent("上次執行", value: timeFmt.string(from: l)) }
                HStack {
                    Button("立即執行（依排程判斷）") { model.requestRunServer() }.disabled(server.isRunning)
                    Menu("強制執行…") {
                        ForEach(AppModel.forceFlags, id: \.env) { f in
                            Button(f.title) { model.requestRunServer(force: [f.env]) }
                        }
                        Divider()
                        Button("全部強制") { model.requestRunServer(force: AppModel.forceFlags.map(\.env)) }
                    }.disabled(server.isRunning)
                    if server.isRunning { Button("中止") { model.stopServer() } }
                }
                Text("排程時間點為「小時是間隔倍數」；實際每項功能是否執行，仍由 server.py 內的 *_SCHEDULE_MODULO 設定判斷。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("App") {
                Toggle("開機時自動啟動", isOn: Binding(get: { model.loginItem }, set: { model.setLoginItem($0) }))
                if let e = model.loginItemError { Text(e).font(.caption).foregroundStyle(.red) }
                Toggle("開啟 App 時顯示主視窗", isOn: $model.showWindowOnLaunch)
            }
        }
        .formStyle(.grouped)
    }
}

struct LogTab: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var tagged: BotRunner
    @ObservedObject private var server: BotRunner
    @State private var which = 0

    init(model: AppModel) {
        self.model = model
        _tagged = ObservedObject(wrappedValue: model.tagged)
        _server = ObservedObject(wrappedValue: model.server)
    }

    private var runner: BotRunner { which == 0 ? tagged : server }

    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Picker("", selection: $which) { Text("標注回覆").tag(0); Text("排程任務").tag(1) }
                    .pickerStyle(.segmented).frame(width: 220).labelsHidden()
                Spacer()
                Button("清除") { runner.clearLogs() }
                Button("在 Finder 顯示日誌檔") {
                    NSWorkspace.shared.open(FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/DiscordAIConcludeBot"))
                }
            }
            ScrollViewReader { proxy in
                ScrollView {
                    Text(runner.logs.joined(separator: "\n"))
                        .font(.system(size: 11, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(8)
                    Color.clear.frame(height: 1).id("end")
                }
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .onChange(of: runner.logs.count) { _, _ in proxy.scrollTo("end") }
            }
        }
    }
}

struct EnvTab: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(EnvStore.file.path.replacingOccurrences(of: NSHomeDirectory(), with: "~"))
                .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            if model.envAvailability == .ready {
                TextEditor(text: $model.envText)
                    .font(.system(size: 12, design: .monospaced))
                    .scrollContentBackground(.hidden)
                    .padding(6)
                    .background(Color(nsColor: .textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                HStack {
                    Button("儲存並重新啟動標注回覆") { model.saveEnv() }.keyboardShortcut("s")
                    Button("重新讀取") { model.refreshEnv() }
                    Button("在 Finder 顯示") { NSWorkspace.shared.activateFileViewerSelecting([EnvStore.file]) }
                    Text(model.envMessage).font(.caption).foregroundStyle(.secondary)
                }
                Text("內容為明碼，存在你的 iCloud Drive；換一台 Mac 登入同一個 iCloud 就能沿用。").font(.caption).foregroundStyle(.secondary)
            } else {
                Spacer()
                VStack(spacing: 10) {
                    Text(model.envMessage).foregroundStyle(.secondary)
                    HStack {
                        Button("重新檢查") { model.refreshEnv() }
                        if model.envAvailability == .missing {
                            Button("建立範本") { model.envText = EnvStore.template; model.saveEnv() }
                        }
                    }
                }.frame(maxWidth: .infinity)
                Spacer()
            }
        }
    }
}

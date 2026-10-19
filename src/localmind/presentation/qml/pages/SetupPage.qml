import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: page
    property bool compact: false
    property bool showModelDetails: false
    Theme { id: theme }
    clip: true
    contentWidth: availableWidth
    ScrollBar.vertical.policy: ScrollBar.AsNeeded
    Item {
        width: page.availableWidth
        height: settings.implicitHeight + 56
        ColumnLayout {
            id: settings
            width: Math.min(760, parent.width - 48)
            anchors.horizontalCenter: parent.horizontalCenter
            y: 28
            spacing: 18
            ColumnLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: 6
                spacing: 7
                Text { text: "Make yourself at home"; color: theme.text; font.pixelSize: 24; font.weight: Font.DemiBold; font.letterSpacing: -0.5 }
                Text { text: "Your workspace, local model, and privacy preferences."; color: theme.secondary; font.pixelSize: 12 }
            }
            BentoCard {
                Layout.fillWidth: true
                title: "Workspace access"
                eyebrow: "Choose the folder LocalMind can work in. File changes always need approval."
                RowLayout {
                    Layout.fillWidth: true
                    AppIcon { name: "folder"; color: theme.secondary; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    Text {
                        Layout.fillWidth: true
                        text: dashboard.workspace || "No workspace selected"
                        textFormat: Text.PlainText
                        color: dashboard.workspace ? theme.text : theme.muted
                        font.pixelSize: 12
                        elide: Text.ElideMiddle
                        HoverHandler { id: folderHover }
                        ToolTip.visible: folderHover.hovered
                        ToolTip.text: dashboard.workspace
                    }
                    AssistantButton { text: dashboard.workspace ? "Change folder" : "Choose folder"; enabled: !dashboard.busy; onClicked: dashboard.chooseWorkspace() }
                }
            }
            BentoCard {
                Layout.fillWidth: true
                title: "Language model"
                eyebrow: "Add semantic matching for more ways to phrase your requests. Core tools work without it."
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text { text: "MiniLM L6 · " + (dashboard.modelDownloadSize / 1000000).toFixed(1) + " MB"; color: theme.text; font.pixelSize: 13; font.weight: Font.Medium }
                        Text { text: dashboard.modelStatus; color: dashboard.modelError.length ? theme.error : theme.secondary; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    }
                    StatusPill {
                        label: dashboard.modelChecking ? "Checking" : dashboard.modelInstalled ? "Ready" : dashboard.modelDownloading ? "Downloading" : "Optional"
                        indicator: dashboard.modelInstalled ? theme.success : dashboard.modelChecking || dashboard.modelDownloading ? theme.accent : theme.muted
                    }
                }
                ProgressBar {
                    Layout.fillWidth: true
                    visible: dashboard.modelDownloading
                    from: 0; to: 100; value: dashboard.modelProgress
                    background: Rectangle { implicitHeight: 4; radius: 2; color: theme.raised }
                    contentItem: Item { implicitHeight: 4; Rectangle { width: parent.width * dashboard.modelProgress / 100; height: 4; radius: 2; color: theme.accent } }
                }
                Text { Layout.fillWidth: true; visible: dashboard.modelError.length > 0; text: dashboard.modelError; textFormat: Text.PlainText; color: theme.error; font.pixelSize: 12; wrapMode: Text.Wrap }
                RowLayout {
                    Layout.fillWidth: true
                    AssistantButton {
                        text: dashboard.modelInstalled ? "Model installed" : dashboard.modelDownloading ? "Downloading…" : "Download model"
                        primary: !dashboard.modelInstalled
                        enabled: !dashboard.modelInstalled && !dashboard.modelDownloading && !dashboard.modelChecking
                        onClicked: dashboard.downloadModel()
                    }
                    AssistantButton { visible: dashboard.modelDownloading; text: "Cancel download"; quiet: true; onClicked: dashboard.cancelModelDownload() }
                    Item { Layout.fillWidth: true }
                    AssistantButton { text: page.showModelDetails ? "Hide details" : "Model details"; quiet: true; onClicked: page.showModelDetails = !page.showModelDetails }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: page.showModelDetails
                    spacing: 10
                    Text { Layout.fillWidth: true; text: "All-MiniLM-L6-v2 · ONNX · Apache-2.0. Model files are verified before use. Downloads contact Hugging Face only when you start them; prompts and file contents are not uploaded."; color: theme.secondary; font.pixelSize: 11; wrapMode: Text.Wrap }
                    Text { Layout.fillWidth: true; text: dashboard.modelPath; textFormat: Text.PlainText; color: theme.muted; font.pixelSize: 11; wrapMode: Text.WrapAnywhere }
                    Text {
                        text: '<a href="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41">View model source ↗</a>'
                        textFormat: Text.RichText
                        linkColor: theme.accent
                        font.pixelSize: 11
                        onLinkActivated: function(link) { Qt.openUrlExternally(link) }
                    }
                }
            }
            BentoCard {
                Layout.fillWidth: true
                title: "History & privacy"
                eyebrow: "Conversations are stored on this device. Extracted file previews aren't retained."
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: "Keep conversations for"; color: theme.text; font.pixelSize: 12 }
                    ComboBox {
                        id: retention
                        objectName: "historyRetention"
                        property var dayValues: [7, 30, 90, 365]
                        model: ["7 days", "30 days", "90 days", "365 days"]
                        currentIndex: dayValues.indexOf(history.retentionDays)
                        enabled: !dashboard.busy && history.ready
                        Accessible.name: "History retention period"
                        onActivated: {
                            history.setRetentionDays(dayValues[currentIndex])
                            currentIndex = dayValues.indexOf(history.retentionDays)
                        }
                        background: Rectangle { implicitWidth: 126; implicitHeight: 36; radius: 8; color: theme.raised; border.color: retention.activeFocus ? theme.accent : theme.border }
                        contentItem: Text { text: retention.displayText; color: theme.text; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 26 }
                        Connections { target: history; function onChanged() { retention.currentIndex = retention.dayValues.indexOf(history.retentionDays) } }
                    }
                    AssistantButton { text: "Clear history…"; quiet: true; enabled: !dashboard.busy && history.ready; onClicked: history.clearHistory() }
                }
                Text { Layout.fillWidth: true; text: "History is local plaintext. Recognized credentials are redacted, but avoid entering secrets. Clearing history preserves model files and photo undo records."; color: theme.muted; font.pixelSize: 11; wrapMode: Text.Wrap; lineHeight: 1.3 }
                Text { Layout.fillWidth: true; visible: history.error.length > 0; text: history.error; textFormat: Text.PlainText; color: theme.error; font.pixelSize: 11; wrapMode: Text.Wrap }
            }
            Text { Layout.fillWidth: true; text: "LocalMind · " + dashboard.runtimeLabel; color: theme.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter }
        }
    }
}

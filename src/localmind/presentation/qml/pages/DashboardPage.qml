import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: page
    property bool compact: false
    signal requestAssistant(string text)
    Theme { id: theme }
    contentWidth: availableWidth
    clip: true
    ScrollBar.vertical.policy: ScrollBar.AsNeeded
    Item {
        width: page.availableWidth
        height: content.implicitHeight + 56
        ColumnLayout {
            id: content
            width: Math.min(1120, parent.width - (page.compact ? 48 : 64))
            anchors.horizontalCenter: parent.horizontalCenter
            y: 28
            spacing: 20
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 7
                Text { text: "A clearer view of your workspace"; color: theme.text; font.pixelSize: 24; font.weight: Font.DemiBold; font.letterSpacing: -0.5 }
                Text {
                    Layout.fillWidth: true
                    text: dashboard.workspace || "Choose a folder to browse files and see activity."
                    textFormat: Text.PlainText
                    color: theme.secondary
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                    HoverHandler { id: pathHover }
                    ToolTip.visible: pathHover.hovered
                    ToolTip.text: dashboard.workspace
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: [
                        { label: "Files shown", value: dashboard.resultCount.toLocaleString() },
                        { label: "Entries checked", value: dashboard.scannedCount.toLocaleString() },
                        { label: "Latest scan", value: dashboard.busy && !assistant.busy ? "Working" : dashboard.scannedCount === 0 ? "Not started" : dashboard.partial ? "Partial" : "Complete" }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 84
                        radius: 12
                        color: theme.surface
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 6
                            Text { text: modelData.label; color: theme.secondary; font.pixelSize: 11 }
                            Text { text: modelData.value; color: theme.text; font.pixelSize: 22; font.weight: Font.Medium; font.letterSpacing: -0.4 }
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: dashboard.error.length > 0
                text: dashboard.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: theme.error
                font.pixelSize: 12
            }
            GridLayout {
                Layout.fillWidth: true
                columns: content.width > 890 ? 2 : 1
                columnSpacing: 20
                rowSpacing: 20
                BentoCard {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 680
                    title: "Workspace files"
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        AssistantButton { text: "List files"; iconName: "folder"; enabled: !dashboard.busy; onClicked: dashboard.listFiles() }
                        AssistantButton { text: "Find PDFs"; enabled: !dashboard.busy; quiet: true; onClicked: dashboard.findPdfs("") }
                        Item { Layout.fillWidth: true }
                        Text { text: dashboard.resultCount + " shown"; color: theme.muted; font.pixelSize: 11 }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: dashboard.resultCount > 0 ? Math.min(380, dashboard.resultCount * 60) : 220
                        ListView {
                            id: fileList
                            objectName: "workspaceFiles"
                            anchors.fill: parent
                            model: dashboard.results
                            clip: true
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: FileRow {
                                objectName: "workspaceFileRow"
                                required property var modelData
                                required property int index
                                width: fileList.width - 12
                                fileInfo: modelData
                                rowIndex: index
                            }
                        }
                        ColumnLayout {
                            anchors.centerIn: parent
                            width: parent.width - 32
                            visible: dashboard.resultCount === 0
                            spacing: 12
                            AppIcon { Layout.alignment: Qt.AlignHCenter; name: "folder"; color: theme.muted; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
                            Text { Layout.fillWidth: true; text: dashboard.busy && !assistant.busy ? "Looking through your folder…" : dashboard.scannedCount > 0 ? "No matching files" : "Your files, at a glance"; color: theme.secondary; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter }
                            Text { Layout.fillWidth: true; text: dashboard.workspace ? "Choose List files or Find PDFs to get started." : "Select a workspace using the folder button above."; color: theme.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap }
                        }
                    }
                    Text { Layout.fillWidth: true; text: dashboard.partial ? "Partial results · The scan reached a limit or skipped entries." : "Filename discovery · Up to 100 results per scan"; color: theme.muted; font.pixelSize: 10; wrapMode: Text.Wrap }
                }
                BentoCard {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 300
                    Layout.alignment: Qt.AlignTop
                    title: "Recent activity"
                    Text { Layout.fillWidth: true; visible: dashboard.activity.length === 0; text: "Completed actions will appear here."; color: theme.secondary; font.pixelSize: 12; wrapMode: Text.Wrap }
                    Repeater {
                        model: dashboard.activity
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 7
                            RowLayout {
                                Layout.fillWidth: true
                                Text { Layout.fillWidth: true; text: modelData.title; textFormat: Text.PlainText; color: theme.text; font.pixelSize: 12; elide: Text.ElideRight }
                                Text { text: modelData.time; color: theme.muted; font.pixelSize: 10 }
                            }
                            Text { Layout.fillWidth: true; text: modelData.outcome; textFormat: Text.PlainText; color: theme.secondary; font.pixelSize: 11 }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#252934"; Layout.topMargin: 5; Layout.bottomMargin: 5 }
                        }
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                Layout.preferredHeight: childrenRect.height
                spacing: 8
                AssistantButton { text: "Analyze folder"; iconName: "folder"; enabled: !dashboard.busy; onClicked: page.requestAssistant("Analyze this folder") }
                AssistantButton { text: "Inspect project"; iconName: "project"; enabled: !dashboard.busy; onClicked: page.requestAssistant("Explain this project") }
                AssistantButton { text: "Organize photos"; iconName: "image"; enabled: !dashboard.busy; onClicked: page.requestAssistant("Help me organize my photos") }
            }
            BentoCard {
                Layout.fillWidth: true
                visible: assistant.resultCards.length > 0
                title: "Latest assistant result"
                Text { Layout.fillWidth: true; text: assistant.resultCards.length > 0 ? assistant.resultCards[assistant.resultCards.length - 1].title : ""; color: theme.text; font.pixelSize: 13 }
                Text { Layout.fillWidth: true; text: assistant.resultCards.length > 0 ? assistant.resultCards[assistant.resultCards.length - 1].detail : ""; textFormat: Text.PlainText; color: theme.secondary; font.pixelSize: 12; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                AssistantButton { text: "Open conversation"; iconName: "arrow"; quiet: true; onClicked: page.requestAssistant("") }
            }
        }
    }
}

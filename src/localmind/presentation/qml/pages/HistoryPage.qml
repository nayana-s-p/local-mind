import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property bool compact: false
    Theme { id: theme }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.compact ? 24 : 32
        spacing: 24
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                Text { text: "Pick up where you left off"; color: theme.text; font.pixelSize: 23; font.weight: Font.DemiBold; font.letterSpacing: -0.5 }
                Text { text: history.conversations.length + (history.conversations.length === 1 ? " conversation" : " conversations") + " · Saved on this device"; color: theme.secondary; font.pixelSize: 12 }
            }
            AssistantButton {
                objectName: "clearHistory"
                text: "Clear history…"
                quiet: true
                enabled: !dashboard.busy && history.ready
                onClicked: history.clearHistory()
            }
        }
        Text {
            Layout.fillWidth: true
            visible: history.error.length > 0
            text: history.error
            textFormat: Text.PlainText
            color: theme.error
            font.pixelSize: 12
            wrapMode: Text.Wrap
        }
        ListView {
            id: conversations
            objectName: "conversationHistoryList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: history.conversations
            clip: true
            spacing: 4
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Button {
                id: row
                required property var modelData
                width: conversations.width - 12
                height: 78
                hoverEnabled: true
                enabled: !dashboard.busy && !history.switching
                Accessible.name: modelData.title + ", " + modelData.messageCount + " messages"
                onClicked: history.openConversation(modelData.id)
                background: Rectangle {
                    radius: 11
                    color: row.modelData.id === history.conversationId ? "#1E1D2B" : row.hovered ? theme.surface : "transparent"
                    border.color: row.activeFocus ? theme.accent : "transparent"
                }
                contentItem: RowLayout {
                    spacing: 16
                    AppIcon { Layout.leftMargin: 12; name: "history"; color: theme.muted; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 7
                        Text { Layout.fillWidth: true; text: row.modelData.title; textFormat: Text.PlainText; color: theme.text; font.pixelSize: 13; elide: Text.ElideRight }
                        Text { text: row.modelData.updated + " · " + row.modelData.messageCount + " messages"; color: theme.secondary; font.pixelSize: 11 }
                    }
                    Text { visible: row.modelData.id === history.conversationId; text: "Current"; color: theme.accent; font.pixelSize: 11 }
                    AppIcon { Layout.rightMargin: 12; name: "chevron"; color: theme.muted; Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
                }
            }
            Text { anchors.centerIn: parent; visible: conversations.count === 0; text: "Your conversations will appear here."; color: theme.secondary; font.pixelSize: 13 }
        }
        Text {
            Layout.fillWidth: true
            text: "Opening a conversation restores messages, not previous actions or approvals."
            color: theme.muted
            font.pixelSize: 11
            wrapMode: Text.Wrap
        }
    }
}

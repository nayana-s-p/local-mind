import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: row
    required property var fileInfo
    property int rowIndex: 0
    Theme { id: theme }
    implicitHeight: 60
    radius: 8
    color: hover.hovered ? theme.raised : "transparent"
    HoverHandler { id: hover }
    Accessible.name: fileInfo.name + ", " + fileInfo.relativePath
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 4
        spacing: 12
        AppIcon { name: "file"; color: theme.muted; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text { Layout.fillWidth: true; text: row.fileInfo.name; textFormat: Text.PlainText; color: theme.text; font.pixelSize: 12; elide: Text.ElideRight }
            Text { Layout.fillWidth: true; visible: row.fileInfo.relativePath !== row.fileInfo.name; text: row.fileInfo.relativePath; textFormat: Text.PlainText; color: theme.muted; font.pixelSize: 10; elide: Text.ElideMiddle }
        }
        Text { text: row.fileInfo.extension.replace(/^\./, "").toUpperCase(); textFormat: Text.PlainText; color: theme.muted; font.pixelSize: 10 }
        AssistantButton {
            iconName: "folder"
            text: ""
            quiet: true
            enabled: !dashboard.busy
            accessibleLabel: "Show " + row.fileInfo.name + " in its folder"
            tooltip: "Show in folder"
            onClicked: dashboard.revealFile(row.fileInfo.relativePath)
        }
    }
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#242833" }
}

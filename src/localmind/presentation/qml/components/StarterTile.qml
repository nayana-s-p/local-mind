import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: tile
    property string title: ""
    property string description: ""
    property string iconName: "folder"
    Theme { id: theme }
    hoverEnabled: true
    Accessible.name: title + ". " + description
    padding: 16
    implicitHeight: 116
    background: Rectangle {
        radius: 13
        color: tile.down ? theme.raised : tile.hovered ? "#1B1E28" : theme.surface
        border.color: tile.activeFocus ? theme.accent : tile.hovered ? "#3B3C50" : "#252934"
        border.width: tile.activeFocus ? 2 : 1
    }
    contentItem: ColumnLayout {
        spacing: 9
        AppIcon { name: tile.iconName; color: theme.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
        Text { text: tile.title; color: theme.text; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Text { text: tile.description; color: theme.secondary; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string glyph: ""
    property bool selected: false
    property bool compact: false
    Theme { id: theme }
    hoverEnabled: true
    Accessible.name: text
    implicitHeight: 42
    ToolTip.visible: compact && hovered
    ToolTip.text: text
    ToolTip.delay: 450
    background: Rectangle {
        radius: 9
        color: control.selected ? theme.accentSurface : control.hovered ? theme.surface : "transparent"
        border.color: control.activeFocus ? theme.accent : "transparent"
        border.width: 2
    }
    contentItem: RowLayout {
        spacing: 12
        AppIcon {
            Layout.leftMargin: control.compact ? 1 : 6
            Layout.alignment: control.compact ? Qt.AlignHCenter : Qt.AlignLeft
            name: control.glyph
            color: control.selected ? theme.accent : theme.secondary
            Layout.preferredWidth: 19
            Layout.preferredHeight: 19
        }
        Text {
            Layout.fillWidth: true
            visible: !control.compact
            text: control.text
            color: control.selected ? theme.text : theme.secondary
            font.pixelSize: 13
            font.weight: control.selected ? Font.DemiBold : Font.Normal
        }
    }
}

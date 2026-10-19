import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property bool primary: false
    property bool quiet: false
    property string iconName: ""
    property string accessibleLabel: text
    property string tooltip: ""
    Theme { id: theme }
    hoverEnabled: true
    implicitHeight: 36
    implicitWidth: contentItem.implicitWidth + leftPadding + rightPadding
    leftPadding: text.length > 0 ? 13 : 9
    rightPadding: text.length > 0 ? 13 : 9
    topPadding: 8
    bottomPadding: 8
    Accessible.name: accessibleLabel
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 550
    contentItem: RowLayout {
        spacing: 8
        AppIcon {
            visible: control.iconName.length > 0
            name: control.iconName
            color: !control.enabled ? theme.muted : control.primary ? "#171421" : theme.secondary
            Layout.preferredWidth: 17
            Layout.preferredHeight: 17
        }
        Text {
            visible: control.text.length > 0
            text: control.text
            textFormat: Text.PlainText
            color: !control.enabled ? theme.muted : control.primary ? "#171421" : theme.text
            font.pixelSize: 12
            font.weight: control.primary ? Font.DemiBold : Font.Medium
            Layout.alignment: Qt.AlignHCenter
        }
    }
    background: Rectangle {
        radius: 9
        color: !control.enabled ? (control.quiet ? "transparent" : theme.surface)
             : control.primary ? (control.down ? "#8B7BE5" : control.hovered ? "#B0A4FF" : theme.accent)
             : control.down ? "#292D39" : control.hovered ? theme.raised : control.quiet ? "transparent" : theme.surface
        border.color: control.activeFocus ? theme.accent : control.primary || control.quiet ? "transparent" : theme.border
        border.width: control.activeFocus ? 2 : 1
    }
}

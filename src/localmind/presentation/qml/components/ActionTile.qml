import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string title: ""
    property string description: ""
    property string glyph: ""
    property color glyphColor: "#A89BFF"
    signal activated()

    implicitHeight: 76
    hoverEnabled: true
    Accessible.name: title + ". " + description
    onClicked: activated()

    background: Rectangle {
        radius: 12
        color: !control.enabled ? "#191C24" : control.down ? "#292D3A" : control.hovered ? "#222633" : "#1D212C"
        border.color: control.activeFocus ? "#8B7CF6" : "#2B303D"
        border.width: control.activeFocus ? 2 : 1
    }

    contentItem: RowLayout {
        spacing: 12
        Rectangle {
            Layout.preferredWidth: 38
            Layout.preferredHeight: 38
            radius: 11
            color: "#28283A"
            Text {
                anchors.centerIn: parent
                text: control.glyph
                color: control.glyphColor
                font.pixelSize: 17
                font.weight: Font.DemiBold
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Text {
                Layout.fillWidth: true
                text: control.title
                color: control.enabled ? "#EEF0F6" : "#878D9A"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: control.description
                color: control.enabled ? "#929AAC" : "#686F7D"
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }
        Text {
            text: "›"
            color: "#777F90"
            font.pixelSize: 20
        }
    }
}


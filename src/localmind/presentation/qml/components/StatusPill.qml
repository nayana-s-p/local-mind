import QtQuick
import QtQuick.Layouts

Rectangle {
    property string label: ""
    property color indicator: "#75C9AB"
    implicitWidth: pillRow.implicitWidth + 20
    implicitHeight: 27
    radius: 8
    color: "#20242E"
    RowLayout {
        id: pillRow
        anchors.centerIn: parent
        spacing: 7
        Rectangle { Layout.preferredWidth: 5; Layout.preferredHeight: 5; radius: 3; color: indicator }
        Text { text: label; color: "#BEC2CF"; font.pixelSize: 11 }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: card
    property string title: ""
    property string eyebrow: ""
    default property alias content: body.data
    Theme { id: theme }
    implicitHeight: cardLayout.implicitHeight + 40
    color: theme.surface
    radius: 14
    border.color: "#232732"
    ColumnLayout {
        id: cardLayout
        anchors.fill: parent
        anchors.margins: 20
        spacing: 18
        ColumnLayout {
            Layout.fillWidth: true
            visible: card.title.length > 0 || card.eyebrow.length > 0
            spacing: 5
            Text {
                Layout.fillWidth: true
                visible: card.title.length > 0
                text: card.title
                textFormat: Text.PlainText
                color: theme.text
                font.pixelSize: 14
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                visible: card.eyebrow.length > 0
                text: card.eyebrow
                textFormat: Text.PlainText
                color: theme.secondary
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 12
        }
    }
}

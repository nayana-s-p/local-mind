import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: composer
    signal submitted(string text)
    Theme { id: theme }
    spacing: 10
    function focusInput() { entry.forceActiveFocus() }
    function send() {
        if (!entry.text.trim().length || history.switching) return
        var value = entry.text
        entry.clear()
        composer.submitted(value)
        entry.forceActiveFocus()
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 66
        radius: 15
        color: theme.surface
        border.color: entry.activeFocus ? "#716697" : "#353A48"
        border.width: 1
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 12
            spacing: 12
            TextField {
                id: entry
                objectName: "assistantInput"
                Layout.fillWidth: true
                maximumLength: 2000
                placeholderText: "Ask LocalMind to do something…"
                placeholderTextColor: theme.muted
                color: theme.text
                font.pixelSize: 14
                selectByMouse: true
                selectionColor: "#635583"
                background: Item {}
                padding: 0
                enabled: !history.switching
                Accessible.name: "Tell LocalMind what to do"
                onAccepted: composer.send()
                Keys.onEscapePressed: focus = false
            }
            AssistantButton {
                objectName: "sendRequest"
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                primary: true
                iconName: "send"
                text: ""
                accessibleLabel: "Send request to LocalMind"
                tooltip: "Send request"
                enabled: entry.text.trim().length > 0 && !history.switching
                onClicked: composer.send()
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 4
        Layout.rightMargin: 4
        Text {
            Layout.fillWidth: true
            text: "Local processing · File changes need your approval"
            color: theme.muted
            font.pixelSize: 10
        }
        Text {
            visible: composer.width > 470
            text: Qt.platform.os === "osx" ? "⌘ K to focus" : "Ctrl K to focus"
            color: theme.muted
            font.pixelSize: 10
        }
    }
}

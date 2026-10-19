import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: panel
    Theme { id: theme }
    readonly property bool wide: width >= 1040
    readonly property bool empty: assistant.messages.length <= 1 && !assistant.busy && !assistant.hasPlan
    function focusComposer() { composer.focusInput() }
    function updateReview() {
        if (!assistant.hasPlan || wide) reviewDrawer.close()
        else reviewDrawer.open()
    }
    onWidthChanged: Qt.callLater(updateReview)
    Connections {
        target: assistant
        function onPlanChanged() { panel.updateReview() }
    }
    RowLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(650, parent.width - 20)
                    visible: panel.empty
                    spacing: 18
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 54
                        Layout.preferredHeight: 54
                        Layout.bottomMargin: 2
                        radius: 18
                        color: theme.accentSurface
                        AppIcon { anchors.centerIn: parent; width: 30; height: 30; name: "assistant"; color: theme.accent }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Make room for what matters."
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        color: theme.text
                        font.pixelSize: panel.width < 800 ? 26 : 30
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.7
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Find a file, understand a folder, or bring a little order to your day."
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        color: theme.secondary
                        font.pixelSize: 13
                        lineHeight: 1.35
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 16
                        columns: width > 570 ? 3 : 1
                        columnSpacing: 10
                        rowSpacing: 10
                        Repeater {
                            model: [
                                { title: "Explore a folder", detail: "See what's taking up space", icon: "folder", prompt: "Analyze this folder" },
                                { title: "Organize photos", detail: "Start with a safe preview", icon: "image", prompt: "Help me organize my photos" },
                                { title: "Understand a project", detail: "Explore its structure and tools", icon: "project", prompt: "Explain this project" }
                            ]
                            delegate: StarterTile {
                                required property var modelData
                                Layout.fillWidth: true
                                title: modelData.title
                                description: modelData.detail
                                iconName: modelData.icon
                                enabled: !dashboard.busy && history.ready
                                onClicked: dashboard.submitCommand(modelData.prompt)
                            }
                        }
                    }
                }
                ListView {
                    id: conversation
                    objectName: "assistantConversation"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(820, parent.width)
                    height: parent.height
                    visible: !panel.empty
                    model: assistant.messages
                    clip: true
                    spacing: 22
                    topMargin: 10
                    bottomMargin: 16
                    property bool followTail: true
                    function showLatest() { if (followTail) positionViewAtEnd() }
                    onCountChanged: { followTail = true; Qt.callLater(showLatest) }
                    onWidthChanged: Qt.callLater(showLatest)
                    onContentHeightChanged: Qt.callLater(showLatest)
                    onMovementStarted: followTail = false
                    onMovementEnded: followTail = atYEnd
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Item {
                        id: message
                        required property var modelData
                        readonly property bool fromUser: modelData.role === "user"
                        width: conversation.width - 14
                        height: messageBody.implicitHeight + 24
                        Accessible.name: (fromUser ? "You" : "LocalMind") + ": " + modelData.text
                        Rectangle {
                            anchors.fill: messageBody
                            anchors.margins: -12
                            visible: message.fromUser
                            radius: 12
                            color: "#1C1E2A"
                        }
                        ColumnLayout {
                            id: messageBody
                            width: message.fromUser ? Math.min(message.width - 40, Math.max(180, message.width * 0.82)) : message.width - 16
                            anchors.right: message.fromUser ? parent.right : undefined
                            anchors.left: message.fromUser ? undefined : parent.left
                            anchors.top: parent.top
                            anchors.topMargin: 12
                            spacing: 8
                            Text {
                                text: message.fromUser ? "You" : "LocalMind"
                                color: message.fromUser ? theme.secondary : theme.accent
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                            TextEdit {
                                Layout.fillWidth: true
                                Layout.preferredHeight: contentHeight
                                text: message.modelData.text
                                textFormat: TextEdit.PlainText
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                color: theme.text
                                font.pixelSize: 13
                                activeFocusOnPress: true
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: 820
                Layout.alignment: Qt.AlignHCenter
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    visible: dashboard.busy
                    BusyIndicator { running: visible; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                    Text { Layout.fillWidth: true; text: assistant.busy ? assistant.status : dashboard.status; textFormat: Text.PlainText; color: theme.secondary; font.pixelSize: 11; elide: Text.ElideRight }
                }
                AssistantButton {
                    visible: assistant.hasPlan && !panel.wide
                    Layout.fillWidth: true
                    text: "Review " + assistant.planCount + " proposed changes"
                    iconName: "check"
                    onClicked: reviewDrawer.open()
                }
                Flow {
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? childrenRect.height : 0
                    visible: !assistant.hasPlan && (assistant.choosingStrategy || assistant.suggestions.length > 0)
                    spacing: 6
                    Repeater {
                        model: assistant.choosingStrategy ? ["By month", "By year", "By file type"] : assistant.suggestions
                        delegate: AssistantButton {
                            required property string modelData
                            text: modelData
                            quiet: true
                            enabled: !dashboard.busy
                            onClicked: assistant.submit(modelData)
                        }
                    }
                }
                CommandComposer { id: composer; Layout.fillWidth: true; onSubmitted: function(text) { dashboard.submitCommand(text) } }
            }
        }
        ActionReview {
            visible: assistant.hasPlan && panel.wide
            Layout.preferredWidth: 340
            Layout.fillHeight: true
        }
    }
    Drawer {
        id: reviewDrawer
        parent: Overlay.overlay
        edge: Qt.RightEdge
        width: Math.min(420, panel.width - 16)
        height: parent.height
        modal: true
        dim: true
        padding: 12
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        enter: Transition {}
        exit: Transition {}
        background: Rectangle { color: theme.background }
        ActionReview {
            anchors.fill: parent
            dismissible: true
            approvalObjectName: "approvePhotoPlanCompact"
            onDismissed: reviewDrawer.close()
        }
    }
}

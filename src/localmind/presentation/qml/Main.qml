import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"
import "pages"

ApplicationWindow {
    id: window
    width: 1440
    height: 900
    minimumWidth: 760
    minimumHeight: 640
    visible: true
    title: "LocalMind"
    color: theme.background
    palette.window: theme.background
    palette.windowText: theme.text
    palette.base: theme.surface
    palette.alternateBase: theme.raised
    palette.text: theme.text
    palette.button: theme.raised
    palette.buttonText: theme.text
    palette.highlight: theme.accentSurface
    palette.highlightedText: theme.text
    palette.placeholderText: theme.muted
    palette.light: theme.border
    palette.mid: theme.border
    palette.dark: theme.background
    property bool compact: width < 1000
    property int currentPage: 0
    readonly property string workspaceName: dashboard.workspace.length > 0
        ? dashboard.workspace.replace(/\\/g, "/").replace(/\/$/, "").split("/").pop() || dashboard.workspace
        : "Choose folder"
    Theme { id: theme }

    function ask(text) {
        currentPage = 0
        if (text.trim().length > 0) dashboard.submitCommand(text)
    }
    Connections {
        target: history
        function onSessionOpened() { window.currentPage = 0 }
    }
    Shortcut {
        sequence: Qt.platform.os === "osx" ? "Meta+K" : "Ctrl+K"
        onActivated: { window.currentPage = 0; assistantPage.focusComposer() }
    }
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: window.compact ? 68 : 208
            color: theme.sidebar
            Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: "#20232C" }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: window.compact ? 12 : 16
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.bottomMargin: 28
                    spacing: 10
                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 11
                        color: theme.accentSurface
                        AppIcon { anchors.centerIn: parent; name: "assistant"; color: theme.accent; width: 22; height: 22 }
                    }
                    Text {
                        visible: !window.compact
                        text: "LocalMind"
                        color: theme.text
                        font.pixelSize: 17
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.4
                    }
                }
                AssistantButton {
                    objectName: "newConversation"
                    Layout.fillWidth: true
                    Layout.bottomMargin: 22
                    text: window.compact ? "" : "New conversation"
                    iconName: "plus"
                    accessibleLabel: "New conversation"
                    tooltip: window.compact ? "New conversation" : ""
                    enabled: history.ready && !dashboard.busy
                    onClicked: history.newConversation()
                }
                Repeater {
                    model: [
                        { label: "Assistant", icon: "assistant", page: 0 },
                        { label: "Dashboard", icon: "dashboard", page: 1 },
                        { label: "History", icon: "history", page: 2 }
                    ]
                    delegate: NavigationButton {
                        required property var modelData
                        objectName: "nav" + modelData.label
                        Layout.fillWidth: true
                        text: modelData.label
                        glyph: modelData.icon
                        compact: window.compact
                        selected: window.currentPage === modelData.page
                        onClicked: window.currentPage = modelData.page
                    }
                }
                Item { Layout.fillHeight: true }
                NavigationButton {
                    objectName: "navSettings"
                    Layout.fillWidth: true
                    text: "Settings"
                    glyph: "settings"
                    compact: window.compact
                    selected: window.currentPage === 3
                    onClicked: window.currentPage = 3
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.bottomMargin: 10
                    height: 1
                    color: "#232630"
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: window.compact ? 16 : 10
                    Layout.bottomMargin: 10
                    spacing: 9
                    Rectangle {
                        width: 6; height: 6; radius: 3
                        color: dashboard.modelChecking ? theme.warning : theme.success
                    }
                    Text {
                        visible: !window.compact
                        text: dashboard.modelChecking ? "Checking local model" : dashboard.modelInstalled ? "Local model ready" : "Local tools ready"
                        color: theme.secondary
                        font.pixelSize: 11
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 76
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: window.compact ? 24 : 32
                    anchors.rightMargin: window.compact ? 24 : 32
                    spacing: 16
                    Text {
                        text: ["Assistant", "Workspace overview", "History", "Settings"][window.currentPage]
                        color: theme.text
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                    AssistantButton {
                        objectName: "workspaceAction"
                        visible: window.currentPage < 2
                        iconName: dashboard.busy ? "stop" : "folder"
                        text: dashboard.busy ? "Stop task" : window.workspaceName.length > 27 ? window.workspaceName.slice(0,24) + "…" : window.workspaceName
                        accessibleLabel: dashboard.busy ? "Stop current task" : "Choose workspace folder"
                        tooltip: dashboard.workspace
                        quiet: true
                        onClicked: {
                            if (assistant.busy) assistant.cancel()
                            else if (dashboard.busy) dashboard.cancelScan()
                            else dashboard.chooseWorkspace()
                        }
                    }
                    AssistantButton {
                        visible: window.currentPage === 0
                        text: ""
                        iconName: "more"
                        quiet: true
                        accessibleLabel: "Conversation actions"
                        tooltip: "Conversation actions"
                        onClicked: conversationMenu.popup()
                        Menu {
                            id: conversationMenu
                            MenuItem {
                                text: "Undo last photo organization…"
                                enabled: !dashboard.busy && dashboard.workspace.length > 0
                                onTriggered: assistant.undoLastOrganization()
                            }
                        }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#20232C" }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: window.currentPage
                AssistantPanel { id: assistantPage }
                DashboardPage {
                    compact: window.compact
                    onRequestAssistant: function(text) { window.ask(text) }
                }
                HistoryPage { compact: window.compact }
                SetupPage { compact: window.compact }
            }
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: review
    property bool dismissible: false
    property string approvalObjectName: "approvePhotoPlan"
    signal dismissed()
    Theme { id: theme }
    color: theme.surface
    radius: 14
    border.color: theme.border
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                width: 30; height: 30; radius: 9; color: theme.accentSurface
                AppIcon { anchors.centerIn: parent; width: 17; height: 17; name: "check"; color: theme.accent }
            }
            Text { Layout.fillWidth: true; text: "Review changes"; color: theme.text; font.pixelSize: 15; font.weight: Font.DemiBold }
            AssistantButton { visible: review.dismissible; text: ""; quiet: true; iconName: "close"; accessibleLabel: "Back to conversation"; onClicked: review.dismissed() }
        }
        Text {
            Layout.fillWidth: true
            text: assistant.planCount + " proposed changes · Not applied yet"
            color: theme.accent
            font.pixelSize: 12
        }
        Text {
            Layout.fillWidth: true
            text: assistant.planScope
            textFormat: Text.PlainText
            color: theme.secondary
            font.pixelSize: 11
            wrapMode: Text.WrapAnywhere
            maximumLineCount: 2
            elide: Text.ElideMiddle
            HoverHandler { id: scopeHover }
            ToolTip.visible: scopeHover.hovered
            ToolTip.text: assistant.planScope
            Accessible.name: "Full scope: " + assistant.planScope
        }
        Text {
            Layout.fillWidth: true
            text: assistant.planSummary
            textFormat: Text.PlainText
            color: theme.secondary
            font.pixelSize: 11
            lineHeight: 1.3
            wrapMode: Text.Wrap
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: theme.border }
        ListView {
            id: moves
            objectName: review.dismissible ? "compactMovePreview" : "photoMovePreview"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: assistant.planModel
            clip: true
            spacing: 0
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Item {
                required property string sourcePath
                required property string destinationPath
                required property string operationKind
                width: moves.width - 12
                height: 72
                Accessible.name: operationKind + " " + sourcePath + " to " + destinationPath
                HoverHandler { id: moveHover }
                ToolTip.visible: moveHover.hovered
                ToolTip.text: operationKind + ": " + sourcePath + "\n→ " + destinationPath
                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 9
                    anchors.bottomMargin: 9
                    spacing: 4
                    Text { Layout.fillWidth: true; text: operationKind.toUpperCase() + " · " + sourcePath; textFormat: Text.PlainText; color: theme.text; font.pixelSize: 11; elide: Text.ElideMiddle }
                    Text { Layout.fillWidth: true; text: "→ " + destinationPath; textFormat: Text.PlainText; color: theme.secondary; font.pixelSize: 11; elide: Text.ElideMiddle }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#242833" }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            AssistantButton {
                objectName: review.approvalObjectName
                Layout.fillWidth: true
                text: "Approve " + assistant.planCount + " changes"
                iconName: "check"
                primary: true
                enabled: assistant.hasPlan && !dashboard.busy
                onClicked: assistant.approvePlan()
            }
            AssistantButton {
                Layout.fillWidth: true
                text: "Discard preview"
                quiet: true
                enabled: !dashboard.busy
                onClicked: assistant.discardPlan()
            }
        }
    }
}

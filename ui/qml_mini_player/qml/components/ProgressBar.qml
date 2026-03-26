import QtQuick 2.15

Item {
    id: root

    property real progress: 0.0
    property color trackColor: "#404040"
    property color progressColor: "#1db954"

    signal seekRequested(real progress)

    height: 4
    implicitHeight: 4

    Rectangle {
        id: track
        anchors.fill: parent
        radius: 2
        color: root.trackColor
    }

    Rectangle {
        id: progressRect
        width: parent.width * Math.max(0, Math.min(1, root.progress))
        height: parent.height
        radius: 2
        color: root.progressColor

        Behavior on width {
            enabled: !mouseArea.pressed
            NumberAnimation { duration: 100 }
        }
    }

    // Handle circle
    Rectangle {
        id: handle
        width: 10
        height: 10
        radius: 5
        color: root.progressColor
        x: progressRect.width - width / 2
        y: (parent.height - height) / 2
        opacity: mouseArea.containsMouse ? 1 : 0

        Behavior on opacity {
            NumberAnimation { duration: 150 }
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        function updateProgress(mouseX) {
            var newProgress = mouseX / width
            newProgress = Math.max(0, Math.min(1, newProgress))
            root.seekRequested(newProgress)
        }

        onClicked: (mouse) => updateProgress(mouse.x)
        onPositionChanged: (mouse) => {
            if (pressed) {
                updateProgress(mouse.x)
            }
        }
    }
}

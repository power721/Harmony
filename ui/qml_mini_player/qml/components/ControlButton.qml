import QtQuick 2.15

Rectangle {
    id: root

    property string icon: ""
    property bool big: false
    property bool isPlaying: false

    width: big ? 40 : 32
    height: width
    radius: width / 2

    color: big ? (mouseArea.containsMouse ? "#1ed760" : "#1db954")
              : (mouseArea.containsMouse ? "#333" : "transparent")

    signal clicked()

    Text {
        anchors.centerIn: parent
        text: root.icon
        color: root.big ? "black" : "white"
        font.pixelSize: root.big ? 18 : 14
        font.bold: root.big
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        onClicked: root.clicked()

        onPressed: root.scale = 0.9
        onReleased: root.scale = 1.0
    }

    Behavior on scale {
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }

    Behavior on color {
        ColorAnimation { duration: 150 }
    }
}

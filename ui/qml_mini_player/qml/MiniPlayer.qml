import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "components"

Window {
    id: window

    width: 350
    height: 150
    visible: true
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    property var bridge: null

    // Drag handling
    property point dragStart: Qt.point(0, 0)
    property bool isDragging: false

    // Shadow layer (behind main content)
    Rectangle {
        anchors.centerIn: parent
        width: parent.width
        height: parent.height
        radius: 16
        color: "#00000000"  // Transparent

        // Multiple shadow layers for blur effect
        Repeater {
            model: 3
            Rectangle {
                anchors.centerIn: parent
                width: parent.width + index * 4
                height: parent.height + index * 4
                radius: parent.radius + index * 2
                color: "#000000"
                opacity: 0.08 - index * 0.02
                z: -index - 1
            }
        }
    }

    Rectangle {
        id: root
        anchors.fill: parent
        radius: 16

        gradient: Gradient {
            GradientStop { position: 0.0; color: "#2a2a2a" }
            GradientStop { position: 1.0; color: "#1f1f1f" }
        }

        // Draggable area
        MouseArea {
            id: dragArea
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            z: 0

            onPressed: (mouse) => {
                window.dragStart = Qt.point(mouse.x, mouse.y)
                window.isDragging = true
            }
            onReleased: {
                window.isDragging = false
            }
            onMouseXChanged: {
                if (window.isDragging) {
                    window.x += mouseX - window.dragStart.x
                }
            }
            onMouseYChanged: {
                if (window.isDragging) {
                    window.y += mouseY - window.dragStart.y
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
            z: 1  // Above drag area

            // Top row: cover, info, close
            RowLayout {
                spacing: 10
                Layout.fillWidth: true

                // Cover art
                Rectangle {
                    id: coverRect
                    width: 50
                    height: 50
                    radius: 8
                    color: "#404040"
                    clip: true

                    Image {
                        id: coverImage
                        anchors.fill: parent
                        source: window.bridge && window.bridge.coverPath ? "file://" + window.bridge.coverPath : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true

                        // Fallback when no image
                        Rectangle {
                            anchors.fill: parent
                            color: "#404040"
                            visible: coverImage.status !== Image.Ready || !coverImage.source

                            Text {
                                anchors.centerIn: parent
                                text: "\u266B"  // Music note
                                font.pixelSize: 20
                                color: "#666"
                            }
                        }
                    }

                    scale: coverMouse.containsMouse ? 1.05 : 1.0
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    MouseArea {
                        id: coverMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        z: 1
                    }
                }

                // Track info
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: window.bridge ? window.bridge.title : "Not Playing"
                        color: "white"
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: window.bridge ? window.bridge.artist : ""
                        color: "#b3b3b3"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Item { Layout.fillWidth: true }

                // Close button
                Rectangle {
                    width: 26
                    height: 26
                    radius: 13
                    color: closeMouse.containsMouse ? "#404040" : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "\u2715"  // ×
                        color: "#b3b3b3"
                        font.pixelSize: 12
                    }

                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        onClicked: {
                            if (window.bridge) {
                                window.bridge.close()
                            }
                        }
                    }

                    Behavior on color {
                        ColorAnimation { duration: 150 }
                    }
                }
            }

            // Progress bar
            ProgressBar {
                id: progressBar
                Layout.fillWidth: true
                progress: window.bridge ? window.bridge.progress : 0

                onSeekRequested: (newProgress) => {
                    if (window.bridge) {
                        window.bridge.seek(newProgress)
                    }
                }
            }

            // Bottom row: time and controls
            RowLayout {
                spacing: 0
                Layout.fillWidth: true

                Text {
                    text: window.bridge ? window.bridge.currentTime : "0:00"
                    color: "#b3b3b3"
                    font.pixelSize: 10
                    font.family: "monospace"
                    Layout.preferredWidth: 35
                }

                Item { Layout.fillWidth: true }

                // Previous button
                ControlButton {
                    icon: "\u23EE"  // ⏮
                    onClicked: {
                        if (window.bridge) {
                            window.bridge.playPrevious()
                        }
                    }
                }

                // Play/Pause button
                ControlButton {
                    icon: window.bridge && window.bridge.playing ? "\u23F8" : "\u25B6"  // ⏸ : ▶
                    big: true

                    onClicked: {
                        if (window.bridge) {
                            window.bridge.togglePlay()
                        }
                    }
                }

                // Next button
                ControlButton {
                    icon: "\u23ED"  // ⏭
                    onClicked: {
                        if (window.bridge) {
                            window.bridge.playNext()
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: window.bridge ? window.bridge.totalTime : "0:00"
                    color: "#b3b3b3"
                    font.pixelSize: 10
                    font.family: "monospace"
                    Layout.preferredWidth: 35
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}

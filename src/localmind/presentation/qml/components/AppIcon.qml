import QtQuick

Canvas {
    id: icon
    property string name: "assistant"
    property color color: "#9A9FAF"
    implicitWidth: 20
    implicitHeight: 20
    onNameChanged: requestPaint()
    onColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d")
        c.reset()
        c.scale(width / 24, height / 24)
        c.strokeStyle = color
        c.lineWidth = 1.65
        c.lineCap = "round"
        c.lineJoin = "round"
        function line(points, close) {
            c.beginPath()
            c.moveTo(points[0][0], points[0][1])
            for (var i = 1; i < points.length; i++) c.lineTo(points[i][0], points[i][1])
            if (close) c.closePath()
            c.stroke()
        }
        if (name === "assistant") {
            line([[12,3],[14.6,9.4],[21,12],[14.6,14.6],[12,21],[9.4,14.6],[3,12],[9.4,9.4]], true)
        } else if (name === "dashboard") {
            c.strokeRect(4,4,6,6); c.strokeRect(14,4,6,6)
            c.strokeRect(4,14,6,6); c.strokeRect(14,14,6,6)
        } else if (name === "history") {
            c.beginPath(); c.arc(12,12,8,0,Math.PI*2); c.stroke()
            line([[12,7],[12,12],[15,14]])
        } else if (name === "settings") {
            line([[4,6],[20,6]]); line([[4,12],[20,12]]); line([[4,18],[20,18]])
            c.fillStyle = "#12141B"
            for (var p of [[9,6],[16,12],[8,18]]) {
                c.beginPath(); c.arc(p[0],p[1],2,0,Math.PI*2); c.fill(); c.stroke()
            }
        } else if (name === "folder") {
            line([[3,7],[3,19],[21,19],[21,7],[12,7],[10,4],[3,4],[3,7]], true)
        } else if (name === "file") {
            line([[6,3],[14,3],[19,8],[19,21],[6,21]],true)
            line([[14,3],[14,8],[19,8]]); line([[9,12],[16,12]]); line([[9,16],[14,16]])
        } else if (name === "image") {
            c.strokeRect(3,4,18,16)
            c.beginPath(); c.arc(8,9,1.5,0,Math.PI*2); c.stroke()
            line([[3,17],[9,12],[12,15],[16,11],[21,16]])
        } else if (name === "project") {
            line([[8,7],[3,12],[8,17]]); line([[16,7],[21,12],[16,17]]); line([[14,4],[10,20]])
        } else if (name === "plus") {
            line([[12,5],[12,19]]); line([[5,12],[19,12]])
        } else if (name === "send") {
            line([[12,19],[12,5]]); line([[6,11],[12,5],[18,11]])
        } else if (name === "arrow") {
            line([[5,12],[19,12]]); line([[14,7],[19,12],[14,17]])
        } else if (name === "chevron") {
            line([[8,5],[15,12],[8,19]])
        } else if (name === "close") {
            line([[6,6],[18,18]]); line([[18,6],[6,18]])
        } else if (name === "stop") {
            c.strokeRect(6,6,12,12)
        } else if (name === "check") {
            line([[5,12],[10,17],[19,7]])
        } else if (name === "more") {
            c.fillStyle = color
            for (var x of [5,12,19]) { c.beginPath(); c.arc(x,12,1,0,Math.PI*2); c.fill() }
        } else if (name === "undo") {
            line([[8,4],[3,9],[8,14]])
            c.beginPath(); c.moveTo(3,9); c.lineTo(14,9); c.bezierCurveTo(23,9,23,21,13,21); c.stroke()
        }
    }
}

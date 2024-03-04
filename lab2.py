import random
from math import factorial
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QGraphicsItem

counter = [1]


class ControlPoint(QtWidgets.QGraphicsObject):
    moved = QtCore.pyqtSignal(int, QtCore.QPointF)
    removeRequest = QtCore.pyqtSignal(object)

    # create a basic, simplified shape for the class
    _base = QtGui.QPainterPath()
    _base.addEllipse(-3, -3, 1, 1)
    _stroker = QtGui.QPainterPathStroker()
    _stroker.setWidth(25)
    _stroker.setDashPattern(QtCore.Qt.DashLine)
    _shape = _stroker.createStroke(_base).simplified()
    # "cache" the boundingRect for optimization
    _boundingRect = _shape.boundingRect()

    def __init__(self, index, pos, parent, prev_point=None, draw_index=None):
        super().__init__(parent)
        self.index = index
        self.setPos(pos)
        self.setFlags(
            self.ItemIsSelectable
            | self.ItemIsMovable
            | self.ItemSendsGeometryChanges
            | self.ItemStacksBehindParent
        )
        self.setZValue(-5)
        self.setToolTip(str(index + 1))
        self.font = QtGui.QFont()
        self.font.setBold(True)
        if self.index == 0:
            self.prev = prev_point
        self.draw_index = draw_index

    def setIndex(self, index):
        self.index = index
        self.setToolTip(str(index + 1))
        self.update()

    def shape(self):
        return self._shape

    def boundingRect(self):
        return self._boundingRect

    def stroker(self):
        return self._stroker

    def base(self):
        return self._base

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            self.moved.emit(self.index, value)
            if self.index == 0 and self.prev is not None:
                self.prev.moved.emit(self.prev.index, value)
                self.prev.setOpacity(0)
                self.setZValue(-50)
        elif change == self.ItemSelectedHasChanged and value:
            # stack this item above other siblings when selected
            for other in self.parentItem().childItems():
                if isinstance(other, self.__class__):
                    other.stackBefore(self)
        return super().itemChange(change, value)

    def paint(self, qp, option, widget=None):
        if self.index in [1, 2]:
            self.stroker().setWidth(15)
            self._shape = self.stroker().createStroke(self.base()).simplified()
            _boundingRect = self.shape().boundingRect()
            qp.setBrush(QtGui.QBrush(QtGui.QColor('green')))
            qp.drawPath(self._shape)
        else:
            qp.setBrush(QtGui.QBrush(QtGui.QColor('red')))
            qp.drawPath(self._shape)
            qp.setPen(QtCore.Qt.white)
            qp.setFont(self.font)
            r = QtCore.QRectF(self.boundingRect())
            r.setSize(r.size() * 2 / 3)
            qp.drawText(r, QtCore.Qt.AlignCenter, str(self.draw_index))
            # self.setZValue(-50)
        if not self.isSelected():
            qp.setPen(QtCore.Qt.NoPen)


class BezierItem(QtWidgets.QGraphicsPathItem):
    _precision = .05
    _delayUpdatePath = False
    _ctrlPrototype = ControlPoint

    def __init__(self, start, end, prev_ctrl=None):
        super().__init__()
        self.setPen(QtGui.QPen(QtCore.Qt.blue, 3, QtCore.Qt.SolidLine))
        self.setZValue(60)
        self.outlineItem = QtWidgets.QGraphicsPathItem(self)
        self.outlineItem.setFlag(self.ItemStacksBehindParent)
        self.outlineItem.setPen(QtGui.QPen(QtCore.Qt.black, 2, QtCore.Qt.DotLine))
        self.outlineItem.setZValue(-10)
        self.outlineItem.setOpacity(0.5)
        self.index = len(counter)
        print(self.index)

        self.controlItems = []
        self._points = []
        self.prev_ctrl = prev_ctrl

        if start is not None and end is not None:
            self.setPoints(start, end)

    def setPoints(self, start, end):
        pointList = [start,
                     ((start[0] + (1 / 3) * end[0]) / (4 / 3), (start[1] + (1 / 3) * end[1]) / (4 / 3) - 30),
                     ((start[0] + 3 * end[0]) / 4, (start[1] + 3 * end[1]) / 4 + 30),
                     end]
        points = []
        for p in pointList:
            if isinstance(p, (QtCore.QPointF, QtCore.QPoint)):
                # always create a copy of each point!
                points.append(QtCore.QPointF(p))
            else:
                points.append(QtCore.QPointF(*p))
        if points == self._points:
            return

        self._points = []
        self.prepareGeometryChange()

        while self.controlItems:
            item = self.controlItems.pop()
            item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(item)
            del item

        self._delayUpdatePath = True
        for i, p in enumerate(points):
            if i == 3:
                counter.append(1)
            self.insertControlPoint(i, p)
        self._delayUpdatePath = False

        self.updatePath()

    def _createControlPoint(self, index, pos):
        ctrlItem = self._ctrlPrototype(index, pos, self, self.prev_ctrl, self.index + (index % 2))
        self.controlItems.insert(index, ctrlItem)
        ctrlItem.moved.connect(self._controlPointMoved)
        ctrlItem.removeRequest.connect(self.removeControlPoint)

    def addControlPoint(self, pos):
        self.insertControlPoint(-1, pos)

    def insertControlPoint(self, index, pos):
        if index < 0:
            index = len(self._points)
        for other in self.controlItems[index:]:
            other.index += 1
            other.update()
        self._points.insert(index, pos)
        self._createControlPoint(index, pos)
        if not self._delayUpdatePath:
            self.updatePath()

    def removeControlPoint(self, cp):
        if isinstance(cp, int):
            index = cp
        else:
            index = self.controlItems.index(cp)

        item = self.controlItems.pop(index)
        self.scene().removeItem(item)
        item.setParentItem(None)
        for other in self.controlItems[index:]:
            other.index -= 1
            other.update()

        del item, self._points[index]

        self.updatePath()

    def precision(self):
        return self._precision

    def setPrecision(self, precision):
        precision = max(.001, min(.5, precision))
        if self._precision != precision:
            self._precision = precision
            self._rebuildPath()

    def stepRatio(self):
        return int(1 / self._precision)

    def setStepRatio(self, ratio):
        '''
        Set the *approximate* number of steps per control point. Note that
        the step count is adjusted to an integer ratio based on the number
        of control points.
        '''
        self.setPrecision(1 / ratio)
        self.update()

    def updatePath(self):
        outlinePath = QtGui.QPainterPath()
        if self.controlItems:
            outlinePath.moveTo(self._points[0])
            for point in self._points[1:]:
                outlinePath.lineTo(point)
        self.outlineItem.setPath(outlinePath)
        self._rebuildPath()

    def _controlPointMoved(self, index, pos):
        self._points[index] = pos
        self.updatePath()

    def _rebuildPath(self):
        '''
        Actually rebuild the path based on the control points and the selected
        curve precision. The default (0.05, ~20 steps per control point) is
        usually enough, lower values result in higher resolution but slower
        performance, and viceversa.
        '''
        self.curvePath = QtGui.QPainterPath()
        if self._points:
            self.curvePath.moveTo(self._points[0])
            count = len(self._points)
            steps = round(count / self._precision)
            precision = 1 / steps
            n = count - 1
            # we're going to iterate through points *a lot* of times; with the
            # small cost of a tuple, we can cache the inner iterator to speed
            # things up a bit, instead of creating it in each for loop cycle
            pointIterator = tuple(enumerate(self._points))
            for s in range(steps + 1):
                u = precision * s
                x = y = 0
                for i, point in pointIterator:
                    binu = (factorial(n) / (factorial(i) * factorial(n - i))
                            * (u ** i) * ((1 - u) ** (n - i)))
                    x += binu * point.x()
                    y += binu * point.y()
                self.curvePath.lineTo(x, y)
        self.setPath(self.curvePath)

    @property
    def points(self):
        return self._points


class BezierExample(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.bezierScene = QtWidgets.QGraphicsScene()
        self.bezierView = QtWidgets.QGraphicsView(self.bezierScene)
        self.bezierView.setRenderHints(QtGui.QPainter.Antialiasing)
        self.bezierItem = BezierItem(
            (300, 100), (450, 100))
        self.bezierScene.addItem(self.bezierItem)
        self.newBezierItem = self.bezierItem
        for i in range(8):
            self.bezierItem = self.newBezierItem
            endPoint = (450+150 * i, 100)
            self.newBezierItem = BezierItem(endPoint, (endPoint[0] + 150, endPoint[1]),
                                            self.bezierItem.controlItems[3])

            self.bezierScene.addItem(self.newBezierItem)

        self.newBezierItem = self.bezierItem
        self.groups = []

        mainLayout = QtWidgets.QVBoxLayout(self)
        topLayout = QtWidgets.QHBoxLayout()
        mainLayout.addLayout(topLayout)

        topLayout.addStretch()
        addButton = QtWidgets.QPushButton('Add point')
        topLayout.addWidget(addButton)

        mainLayout.addWidget(self.bezierView)

        self.bezierView.installEventFilter(self)
        addButton.clicked.connect(self.addPoint)

    def addPoint(self, point=None):
        self.bezierItem = self.newBezierItem
        endPoint = (self.bezierItem.points[3].x(), self.bezierItem.points[3].y())
        self.newBezierItem = BezierItem(endPoint, (endPoint[0] + 200, endPoint[1] + 100), self.bezierItem.controlItems[3])

        self.bezierScene.addItem(self.newBezierItem)

    def eventFilter(self, obj, event):
        if event.type() == event.MouseButtonDblClick:
            pos = self.bezierView.mapToScene(event.pos())
            self.addPoint(pos)
            return True
        return super().eventFilter(obj, event)

    def sizeHint(self):
        return QtWidgets.QApplication.primaryScreen().size() * 2 / 3


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ex = BezierExample()
    ex.show()
    app.exec_()

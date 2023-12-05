import unittest

import maya.cmds as mc

from mayanode import Node, exceptions


class TestNode(unittest.TestCase):
    def testExists(self):
        self.assertTrue(Node('lambert1').exists)
        temp = mc.polyCube()[0]
        n = Node(temp)
        self.assertTrue(n.exists)
        mc.delete(temp)
        self.assertFalse(n.exists)
        with self.assertRaises(exceptions.NodeNotFoundError):
            Node(temp)

    def testName(self):
        self.assertEqual(Node('lambert1').name, 'lambert1')
        new = mc.createNode('transform')
        node = Node(new)
        self.assertEqual(node.name, 'transform1')
        node.name = 'transform2'
        self.assertEqual(node.name, 'transform2')
        node.name = 'transform-3'
        self.assertEqual(node.name, 'transform_3')
        mc.delete(node.name)

    def testUniqueShortName(self):
        transform = mc.polyCube()[0]
        shape = mc.listRelatives(children=True)[0]
        node = Node(transform)
        self.assertEqual(node.name, transform)
        mc.rename(shape, transform)
        self.assertNotEqual(node.name, transform)
        mc.delete(node.name)

    def testNested(self):
        self.assertEqual(Node('lambert1').name, Node(Node('lambert1')).name)

    def testType(self):
        self.assertEqual(Node('lambert1').type, 'lambert')
        new = mc.createNode('transform')
        self.assertEqual(Node(new).type, 'transform')
        mc.delete(new)

    def testCreate(self):
        node = Node.create('transform')
        self.assertEqual(mc.nodeType(node.name), 'transform')
        self.assertEqual(node.name, 'transform1')
        self.assertIsNone(node.parent)
        child = Node.create('locator', name='child')
        self.assertIsNotNone(child.parent)
        self.assertIsNone(child.parent.parent)
        child.parent.parent = node

        shader = Node.create('blinn')
        self.assertEqual(mc.nodeType(shader.name), 'blinn')
        self.assertTrue(mc.attributeQuery('color', node=shader.name, exists=True))

        sg = Node.create('shadingEngine')
        self.assertEqual(mc.nodeType(sg.name), 'shadingEngine')
        self.assertTrue(mc.attributeQuery('surfaceShader', node=sg.name, exists=True))

        mc.delete('transform1', shader.name, sg.name)

    def testParent(self):
        child = Node(mc.createNode('transform'))
        parent = Node(mc.createNode('transform'))
        self.assertIsNone(child.parent)
        child.parent = parent
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.longName, '|{}|{}'.format(parent, child))
        child.parent.name = 'parent1'
        self.assertEqual(child.longName, '|parent1|{}'.format(child))
        parent.name = 'parent2'
        self.assertEqual(child.longName, '|parent2|{}'.format(child))
        child.parent = None
        self.assertEqual(child.longName, '|{}'.format(child))
        with self.assertRaises(exceptions.AlreadyIsChildError):
            child.parent = ''

        child.parent = 'parent2'
        mc.delete('parent2')
        self.assertFalse(child.exists)

    def testChildren(self):
        self.assertEqual(Node('persp').children, ['perspShape'])
        self.assertEqual(Node('lambert1').children, [])

    def testShape(self):
        self.assertEqual(Node('persp').shape, 'perspShape')
        self.assertIsNone(Node('lambert1').shape)

    def testInstances(self):
        node = Node(mc.polyCube(name='instTest1')[0])
        shape = node.shape
        self.assertFalse(node.instanced)
        self.assertFalse(shape.instanced)
        inst = node.instance(name='newInst')
        self.assertFalse(node.instanced)
        self.assertTrue(shape.instanced)
        self.assertFalse(inst.instanced)
        self.assertTrue(inst.shape.instanced)
        self.assertEqual(node.name, 'instTest1')
        self.assertEqual(inst.name, 'newInst')
        mc.delete(node, inst)

    def testInstanceHash(self):
        node = Node(mc.polyCube(name='instTest1')[0])
        self.assertEqual(node.instances, ['instTest1'])
        inst = node.instance()
        self.assertEqual(node.shape, inst.shape)
        self.assertIsNot(node.shape, inst.shape)
        self.assertEqual(len({node.shape, inst.shape}), 1)
        mc.delete(node, inst)

    def testInstanceNames(self):
        node = Node(mc.polyCube(name='instTest1')[0])
        inst = node.instance()
        nodeShape = node.shape
        instanceShape = inst.shape

        self.assertEqual(nodeShape.name, 'instTest1|instTest1Shape')
        self.assertEqual(len(nodeShape._dagPaths), 1)
        self.assertEqual(nodeShape.names, ['instTest1|instTest1Shape', 'instTest2|instTest1Shape'])
        self.assertEqual(len(nodeShape._dagPaths), 2)
        self.assertEqual(nodeShape.longNames, ['|instTest1|instTest1Shape', '|instTest2|instTest1Shape'])
        self.assertEqual(nodeShape.name, 'instTest1|instTest1Shape')

        self.assertEqual(instanceShape.name, 'instTest2|instTest1Shape')
        self.assertEqual(len(instanceShape._dagPaths), 1)
        self.assertEqual(instanceShape.names, ['instTest2|instTest1Shape', 'instTest1|instTest1Shape'])
        self.assertEqual(len(instanceShape._dagPaths), 2)
        self.assertEqual(instanceShape.longNames, ['|instTest2|instTest1Shape', '|instTest1|instTest1Shape'])
        self.assertEqual(instanceShape.name, 'instTest2|instTest1Shape')

        inst.name = 'instRename'
        nodeShape.name = 'instNewShape'
        self.assertEqual(nodeShape.longNames, ['|instTest1|instNewShape', '|instRename|instNewShape'])
        self.assertEqual(instanceShape.longNames, ['|instRename|instNewShape', '|instTest1|instNewShape'])
        mc.delete(node, inst)

    def testInstanceList(self):
        node = Node(mc.polyCube(name='instTest1')[0])

        self.assertEqual(node.instances, ['instTest1'])
        self.assertEqual(node.shape.instances, ['instTest1Shape'])

        inst = node.instance()
        self.assertEqual(node.instances, ['instTest1'])
        self.assertEqual(node.shape.instances, ['instTest1|instTest1Shape', 'instTest2|instTest1Shape'])

        mc.delete(node)
        self.assertEqual(inst.shape.instances, ['instTest1Shape'])
        mc.delete(inst)

    def testInstanceNameNonDag(self):
        node = Node('time1')
        self.assertEqual(node.name, 'time1')
        self.assertEqual(node.names, ['time1'])
        self.assertEqual(node.longNames, ['time1'])

    def testShadingEngine(self):
        node = Node(mc.polyCube(name='shadingEngineTest')[0])
        self.assertEqual(node.shadingEngine, 'initialShadingGroup')

        material = mc.shadingNode('lambert', asShader=True)
        sg = mc.sets(empty=True, renderable=True, noSurfaceShader=True)
        mc.connectAttr(material + '.outColor', sg + '.surfaceShader')

        node.shadingEngine = sg
        self.assertEqual(node.shadingEngine, sg)

        mc.delete(sg, material, node.name)

    def testDelete(self):
        node = Node(mc.createNode('transform'))
        self.assertTrue(node.exists)
        node.delete()
        self.assertFalse(node.exists)
        with self.assertRaises(exceptions.DeleteNodeError):
            node.delete()

    def testTranslate(self):
        node = Node(mc.polyCube()[0])
        self.assertEqual(node.translation.x, 0)
        node.translate(10, 0, 0)
        self.assertEqual(node.translation.x, 10)
        node.translate(-10, 0, 0)
        self.assertEqual(node.translation.x, 0)
        node.translation = (-20, 0, 0)
        node.translate(10, 0, 0)
        self.assertEqual(node.translation.x, -10)
        mc.delete(node)

    def testRotate(self):
        node = Node(mc.polyCube()[0])
        self.assertEqual(node.rotation.x, 0)
        node.rotate(10, 0, 0)
        self.assertEqual(node.rotation.x, 10)
        node.rotate(-10, 0, 0)
        self.assertEqual(node.rotation.x, 0)
        node.rotation = (15, 0, 0)
        node.rotate(-10, 0, 0)
        self.assertEqual(node.rotation.x, 5)
        mc.delete(node)

    def testScale(self):
        node = Node(mc.polyCube()[0])
        self.assertEqual(node.scaling.x, 1)
        node.scale(2, 0, 0)
        self.assertEqual(node.scaling.x, 2)
        node.scale(0.5, 0, 0)
        self.assertEqual(node.scaling.x, 1)
        node.scaling = (0.25, 0, 0)
        node.scale(2, 0, 0)
        self.assertEqual(node.scaling.x, 0.5)
        mc.delete(node)

    def testNamespace(self):
        node = Node(mc.polyCube(name='namespaceTest')[0])
        self.assertEqual(node.namespace, '')

        node.namespace = 'new:namespace'
        self.assertEqual(node.namespace, 'new:namespace')
        self.assertEqual(node.name, 'new:namespace:namespaceTest')
        self.assertEqual(node.longName, '|new:namespace:namespaceTest')

        node.namespace = None
        self.assertEqual(node.namespace, '')
        self.assertEqual(node.name, 'namespaceTest')

        node.namespace = ''
        self.assertEqual(node.namespace, '')

        mc.delete(node.name)
        mc.namespace(removeNamespace='new:namespace')

    def testNamespaceRename(self):
        node = Node(mc.polyCube(name='namespaceTest1')[0])
        node.namespace = 'new:namespace'
        node.parent = 'persp'
        node.name = 'namespaceTest2'
        self.assertEqual(node.namespace, 'new:namespace')
        self.assertEqual(node.parent.namespace, '')

        mc.delete(node.name)
        mc.namespace(removeNamespace='new:namespace')


class TestBoundingBox(unittest.TestCase):

    def testAttrs(self):
        pCube = Node(mc.polyCube()[0])
        self.assertEqual(pCube.boundingBox, (-0.5, -0.5, -0.5, 0.5, 0.5, 0.5))
        self.assertEqual(pCube.boundingBox.x, 0)
        self.assertEqual(pCube.boundingBox.xMin, -0.5)
        self.assertEqual(pCube.boundingBox.width, 1)

        mc.setAttr(pCube.name + '.scaleX', 2)
        self.assertEqual(pCube.boundingBox.xMin, -1)
        self.assertEqual(pCube.boundingBox.x, 0)
        self.assertEqual(pCube.boundingBox.width, 2)

        mc.setAttr(pCube.name + '.translateX', 1)
        self.assertEqual(pCube.boundingBox.x, 1)
        self.assertEqual(pCube.boundingBox.xMin, 0)
        self.assertEqual(pCube.boundingBox.width, 2)

        mc.delete(pCube.name)

    def testOld(self):
        pCube = Node(mc.polyCube()[0])
        boundingBox = pCube.boundingBox
        self.assertEqual(boundingBox, pCube.boundingBox)
        mc.move(1, 1, 1, pCube)
        self.assertNotEqual(boundingBox, pCube.boundingBox)
        mc.delete(pCube)

    def testImmutable(self):
        boundingBox = Node('persp').boundingBox
        with self.assertRaises(AttributeError):
            boundingBox.x = 0

    def testNoSize(self):
        inf = Node(mc.createNode('transform'))
        with self.assertRaises(exceptions.NoBoundingBoxError):
            inf.boundingBox
        mc.delete(inf.name)

    def testCube(self):
        pCube = Node(mc.polyCube()[0])
        boundingBox = pCube.boundingBox
        bbCube1 = boundingBox.drawCube()
        self.assertEqual(bbCube1.boundingBox, boundingBox)

        mc.rotate(32, 72, 47, pCube)
        bbCube2 = pCube.boundingBox.drawCube()
        self.assertNotEqual(bbCube2.boundingBox, boundingBox)

        mc.delete(pCube, bbCube1, bbCube2)


class TestAttr(unittest.TestCase):
    def setUp(self):
        self.node = Node('lambert1')

    def testExists(self):
        self.assertTrue(self.node.attrs['diffuse'].exists)
        self.assertFalse(self.node.attrs['something'].exists)

    def testConcatenate(self):
        self.assertEqual(self.node.attrs['color'], 'lambert1.color')
        self.assertEqual(str(self.node + '.color'), 'lambert1.color')
        self.assertEqual(self.node.attrs['colo'] + 'r', 'lambert1.color')

        with self.assertRaises(exceptions.NodeNotFoundError):
            self.node + '0.color'
        mc.createNode('lambert', name='lambert10')
        self.assertEqual(self.node + '0.color', 'lambert10.color')
        mc.delete('lambert10')

    def testGet(self):
        self.assertEqual(self.node.attrs['color'], 'lambert1.color')
        self.assertEqual(self.node.attrs['color'].value, [(0.5, 0.5, 0.5)])
        self.assertEqual(self.node.attrs['colorR'].value, 0.5)

    def testLock(self):
        self.node.attrs['diffuse'].locked = True
        with self.assertRaises(RuntimeError):
            self.node.attrs['diffuse'] = 0
        self.node.attrs['diffuse'].locked = False

    def testKeyable(self):
        mc.setAttr('lambert1.colorR', keyable=True)
        self.assertTrue(self.node.attrs['colorR'].keyable)
        self.node.attrs['colorR'].keyable = False
        self.assertFalse(self.node.attrs['colorR'].keyable)
        self.node.attrs['colorR'].keyable = True

    def testConnections(self):
        self.assertIn('initialShadingGroup.surfaceShader', self.node.attrs['outColor'].connections)
        self.assertEqual(self.node.attrs['colorR'].connections, [])

    def testList(self):
        self.assertIn('outColor', list(self.node.attrs))
        self.assertNotIn('test', list(self.node.attrs))

    def testType(self):
        self.assertEqual(self.node.attrs['colorR'].type, float)
        self.assertEqual(self.node.attrs['color'].type, (float, float, float))

    def testParentRename(self):
        cube = Node(mc.polyCube()[0])
        tx = cube.attrs['translateX']
        cube.name = 'rename'
        self.assertEqual(str(tx), str(cube.attrs['translateX']))
        mc.delete(cube)

    def testContains(self):
        attrs = Node('lambert1').attrs
        self.assertEqual(dict.__len__(attrs), 0)
        self.assertNotIn('test', attrs)
        self.assertEqual(dict.__len__(attrs), 0)
        self.assertIn('color', attrs)
        self.assertEqual(dict.__len__(attrs), 1)
        self.assertTrue(len(attrs) > 1)
        self.assertTrue(dict.__len__(attrs) > 1)


class TestKeyframes(unittest.TestCase):
    def setUp(self):
        self.oldX = mc.getAttr('persp.translateX')
        mc.setKeyframe('persp.translateX', time=(1, 10), value=-10)
        self.keyframes = Node('persp').attrs['translateX'].keyframes

    def tearDown(self):
        mc.cutKey('persp', attribute='translateX', time=(1, 10))
        mc.setAttr('persp.translateX', self.oldX)

    def testGet(self):
        self.assertEqual(self.keyframes.keys(), [1.0, 10.0])
        self.assertEqual(self.keyframes.values(), [-10, -10])
        self.assertEqual(list(self.keyframes.items()), list(zip(self.keyframes.keys(), self.keyframes.values())))
        self.assertEqual(self.keyframes, {1.0: -10, 10.0: -10})
        self.assertEqual(self.keyframes[1].value, -10)
        self.assertEqual(self.keyframes[1.0].value, -10)
        self.assertIsNone(self.keyframes[2].value)

    def testSet(self):
        self.keyframes[2] = 10
        self.keyframes[3].set(20)
        self.assertEqual(self.keyframes[1].value, -10)
        self.assertEqual(self.keyframes[2].value, 10)
        self.assertEqual(self.keyframes[3].value, 20)
        self.assertIsNone(self.keyframes[4].value)

    def testDelete(self):
        self.assertEqual(self.keyframes[1].value, -10)
        del self.keyframes[1]
        self.assertIsNone(self.keyframes[1].value)

        self.assertEqual(self.keyframes[10].value, -10)
        self.keyframes[10].delete()
        self.assertIsNone(self.keyframes[10].value)


if __name__ == '__main__':
    unittest.main()

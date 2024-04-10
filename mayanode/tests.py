import unittest

import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

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

    def testEquality(self):
        self.assertEqual(Node('lambert1'), Node('lambert1'))
        self.assertEqual(Node('lambert1'), 'lambert1')

        node = Node(mc.createNode('transform', name='equalityTest1'))

        self.assertEqual(node, 'equalityTest1')
        self.assertEqual(node, '|equalityTest1')

        parent = mc.createNode('transform', name='equalityGroup1')
        node.parent = parent

        self.assertEqual(node, 'equalityTest1')
        self.assertNotEqual(node, '|equalityTest1')

        node2 = Node(mc.createNode('transform', name='equalityTest1'))
        self.assertEqual(node, 'equalityTest1')
        self.assertEqual(node2, 'equalityTest1')
        self.assertNotEqual(node, '|equalityTest1')
        self.assertEqual(node2, '|equalityTest1')

        self.assertEqual(node, '|equalityGroup1|equalityTest1')
        self.assertEqual(node, 'equalityGroup1|equalityTest1')

        mc.delete(node, node2, parent)

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

    def testParentGet(self):
        node, pCube = Node.ls(mc.polyCube(name='testParent'))

        self.assertIsNone(node.parent)
        self.assertEqual(node, node.shape.parent)
        node.parent = 'persp'
        self.assertEqual(node, node.shape.parent)
        self.assertEqual(node.parent, 'persp')

        self.assertIsNone(pCube.parent)
        with self.assertRaises(exceptions.NotADagNodeError):
            pCube.parent = 'persp'

        mc.delete(node)

    def testParentSet(self):
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

    def testAncestors(self):
        child = Node(mc.createNode('transform', name='ancestorChild'))
        parent = Node(mc.createNode('transform', name='ancestorParent'))
        root = Node(mc.createNode('transform', name='ancestorRoot'))
        child.parent = parent
        parent.parent = root

        self.assertEqual(child.ancestors[0], parent)
        self.assertEqual(child.ancestors[-1], root)
        self.assertEqual(child.ancestors, [parent, root])
        self.assertFalse(root.ancestors)

        mc.delete(root)

    def testAncestorsIndividual(self):
        child = Node(mc.createNode('transform', name='ancestorChild'))
        parent = Node(mc.createNode('transform', name='ancestorParent'))
        group = Node(mc.createNode('transform', name='ancestorGroup'))
        root = Node(mc.createNode('transform', name='ancestorRoot'))
        child.parent = parent
        parent.parent = group
        group.parent = root

        ancestors = child.ancestors
        self.assertEqual(ancestors[0], parent)
        self.assertEqual(ancestors[1], group)
        self.assertEqual(ancestors, [parent, group, root])

        ancestors = child.ancestors
        self.assertEqual(ancestors[1], group)
        self.assertEqual(ancestors[-1], root)
        self.assertEqual(ancestors, [parent, group, root])

        mc.delete(root)

    def testDescendents(self):
        child1 = Node(mc.createNode('transform', name='descendentChild1'))
        child2 = Node(mc.createNode('transform', name='descendentChild2'))
        parent = Node(mc.createNode('transform', name='descendentParent'))
        root = Node(mc.createNode('transform', name='descendentRoot'))

        child1.parent = child2.parent = parent
        parent.parent = root

        self.assertEqual(root.descendents, [parent, child1, child2])
        self.assertEqual(parent.descendents, [child1, child2])

        mc.delete(root)

    def testTransformShape(self):
        node = Node(mc.polyCube(name='shapeTest')[0])
        self.assertIsNone(node.transform)
        shape = node.shape
        self.assertEqual(shape, 'shapeTestShape')
        self.assertIsNone(shape.shape)
        self.assertEqual(shape.transform, node)

        self.assertIsNone(Node('lambert1').shape)
        self.assertIsNone(Node('lambert1').transform)
        mc.delete(node)

    def testInvalidShape(self):
        grp = Node(mc.group(mc.polyCube(name='shapeTest'), name='shapeTestGrp'))
        self.assertIsNone(grp.shape)
        mc.delete(grp)

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
        self.assertEqual(len({node.shape, inst.shape}), 2)
        mc.delete(node, inst)

    def testInstanceList(self):
        node = Node(mc.polyCube(name='instTest1')[0])
        shape = node.shape

        self.assertEqual(node.instances, ['instTest1'])
        self.assertEqual(shape.instances, ['instTest1Shape'])

        inst = node.instance()
        self.assertEqual(node.instances, ['instTest1'])
        self.assertEqual(shape.instances, ['instTest1|instTest1Shape', 'instTest2|instTest1Shape'])

        instShape = inst.shape
        instA, instB = instShape.instances
        self.assertEqual(instShape, instA)
        self.assertEqual(instShape, instB)

        mc.delete(node)
        self.assertEqual(inst.shape.instances, ['instTest1Shape'])
        mc.delete(inst)

    def testInstanceNonDag(self):
        node = Node('time1')
        self.assertEqual(node.name, 'time1')
        self.assertEqual(node.instances, ['time1'])

    def testInstanceDelete(self):
        node = Node(mc.polyCube(name='instDeleteTest1')[0])
        inst = node.instance()
        shape = node.shape
        self.assertEqual(shape.instances, [node.shape, inst.shape])
        mc.delete(shape)
        self.assertFalse(shape.instances)
        mc.delete(node, inst)

    def testVisibility(self):
        self.assertFalse(Node('lambert1').visible)

        transform = Node(mc.polyCube(name='visibilityTest')[0])
        shape = transform.shape
        inst = transform.instance(name='visibilityInstanceTest')
        instShape = inst.shape

        self.assertTrue(transform.visible)
        self.assertTrue(shape.visible)
        self.assertTrue(inst.visible)
        self.assertTrue(instShape.visible)

        shape.attrs['visibility'] = False

        self.assertTrue(transform.visible)
        self.assertFalse(shape.visible)
        self.assertTrue(inst.visible)
        self.assertFalse(instShape.visible)

        shape.attrs['visibility'] = True
        transform.attrs['visibility'] = False

        self.assertFalse(transform.visible)
        self.assertFalse(shape.visible)
        self.assertTrue(inst.visible)
        self.assertTrue(instShape.visible)

        mc.delete(transform, inst)

    def testShadingEngine(self):
        node = Node(mc.polyCube(name='shadingEngineTest')[0])
        self.assertEqual(node.shadingEngine, None)
        self.assertEqual(node.shape.shadingEngine, 'initialShadingGroup')

        material = mc.shadingNode('lambert', asShader=True)
        sg = mc.sets(empty=True, renderable=True, noSurfaceShader=True)
        mc.connectAttr(material + '.outColor', sg + '.surfaceShader')

        node.shadingEngine = sg
        self.assertEqual(node.shadingEngine, None)
        self.assertEqual(node.shape.shadingEngine, sg)

        node.shape.shadingEngine = 'initialShadingGroup'
        self.assertEqual(node.shadingEngine, None)
        self.assertEqual(node.shape.shadingEngine, 'initialShadingGroup')

        mc.delete(sg, material, node.name)

    def testDelete(self):
        node = Node(mc.createNode('transform'))
        self.assertTrue(node.exists)
        node.delete()
        self.assertFalse(node.exists)
        with self.assertRaises(exceptions.NodeDeletedError):
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
        mc.namespace(removeNamespace='new')

    def testNamespaceRename(self):
        node = Node(mc.polyCube(name='namespaceTest1')[0])
        node.namespace = 'new:namespace'
        node.parent = 'persp'
        node.name = 'namespaceTest2'
        self.assertEqual(node.namespace, 'new:namespace')
        self.assertEqual(node.parent.namespace, '')

        mc.delete(node.name)
        mc.namespace(removeNamespace='new:namespace')
        mc.namespace(removeNamespace='new')

    def testDeleted(self):
        node = Node(mc.polyCube(name='deleteTest')[0])
        mc.delete(node)

        self.assertEqual(node.name, 'deleteTest')

        with self.assertRaises(exceptions.NodeDeletedError):
            node.name = 'renamed'
        with self.assertRaises(exceptions.NodeDeletedError):
            node.longName
        with self.assertRaises(exceptions.NodeDeletedError):
            node.type
        with self.assertRaises(exceptions.NodeDeletedError):
            node.rotation
        with self.assertRaises(exceptions.NodeDeletedError):
            node.rotation = (0, 0, 0)
        with self.assertRaises(exceptions.NodeDeletedError):
            node.namespace
        with self.assertRaises(exceptions.NodeDeletedError):
            node.namespace = 'test'
        with self.assertRaises(exceptions.NodeDeletedError):
            node.attrs.keys()

        self.assertFalse(node.shape)
        self.assertIsNone(node.parent)
        self.assertFalse(node.parents)
        self.assertFalse(node.children)

        with self.assertRaises(exceptions.NodeDeletedError):
            node.instance()
        self.assertFalse(node.instanced)

        with self.assertRaises(exceptions.NodeDeletedError):
            node.shadingEngine = 'test'
        self.assertIsNone(node.shadingEngine)

    def testComparison(self):
        transform, shape = mc.polyCube(name='comparisonTest')
        long = mc.ls(transform, long=True)[0]
        node = Node(transform)
        self.assertEqual(node.name, transform)
        self.assertNotEqual(node.name, long)
        self.assertNotEqual(node.name, shape)
        self.assertEqual(node, transform)
        self.assertEqual(node, long)
        self.assertNotEqual(node, shape)
        mc.delete(transform)

    def testDescendents(self):
        cube = mc.polyCube(name='descendentTest1')[0]
        cube2 = Node(cube).instance(name='descendentTest2')
        group = mc.group(cube, cube2, name='descendentTest3')
        group2 = Node(group).instance(name='descendentTest4')
        overall = mc.group(group, group2, name='descendentTest5')
        self.assertEqual(len(Node(overall).descendents), len(mc.listRelatives(overall, allDescendents=True)))
        mc.delete(cube, cube2, group, group2, overall)

    def testNumVertices(self):
        node = Node(mc.polyCube(name='verticesTest')[0])
        self.assertIsNone(node.api.mesh)
        self.assertIsNotNone(node.shape.api.mesh)
        self.assertEqual(node.shape.api.mesh.numVertices, 8)
        mc.select('verticesTest.vtx[0:7]')
        mel.eval('polyDeleteVertex')
        self.assertEqual(node.shape.api.mesh.numVertices, 0)
        mc.delete(node)

    def testNoMeshGeo(self):
        mesh = Node(mc.createNode('mesh', name='noGeometryTest'))
        self.assertEqual(mesh.type, 'mesh')
        self.assertIsNone(mesh.api.mesh)
        self.assertEqual(mesh.faces, [])
        self.assertEqual(str(mesh.faces), 'noGeometryTest.f[0:0]')
        mc.delete(mesh.parent)


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
        with self.assertRaises(exceptions.AttributeNotFoundError):
            self.node.attrs['something']

    def testExistsIn(self):
        self.assertIn('diffuse', self.node.attrs)
        self.assertNotIn('something', self.node.attrs)

    def testConcatenate(self):
        self.assertEqual(self.node.attrs['color'], 'lambert1.color')
        self.assertEqual(str(self.node + '.color'), 'lambert1.color')
        self.assertEqual(self.node.attrs['color'] + 'R', 'lambert1.colorR')
        with self.assertRaises(exceptions.AttributeNotFoundError):
            self.node.attrs['color'] + 'Y'

        with self.assertRaises(exceptions.NodeNotFoundError):
            self.node + '0.color'
        mc.createNode('lambert', name='lambert10')
        self.assertEqual(self.node + '0.color', 'lambert10.color')
        mc.delete('lambert10')

    def testGet(self):
        self.assertEqual(self.node.attrs['color'], 'lambert1.color')
        self.assertEqual(self.node.attrs['color'].value, (0.5, 0.5, 0.5))
        self.assertEqual(self.node.attrs['colorR'].value, 0.5)

    def testSet(self):
        self.node.attrs['color'] = (1, 2, 1.0)
        self.assertEqual(self.node.attrs['colorR'].value, 1)
        self.node.attrs['colorR'] = 0.5
        self.assertEqual(self.node.attrs['color'].value, (0.5, 2.0, 1.0))
        self.node.attrs['color'] = [0.5] * 3

    def testTypes(self):
        self.assertEqual(self.node.attrs['color'].type, (float, float, float))
        self.assertEqual(self.node.attrs['colorR'].type, float)
        self.assertEqual(self.node.attrs['diffuse'].type, float)
        self.assertEqual(self.node.attrs['hideSource'].type, bool)
        self.assertEqual(self.node.attrs['matteOpacityMode'].type, 'enum')

    def testLock(self):
        self.node.attrs['diffuse'].locked = True
        with self.assertRaises(exceptions.AttributeLockedError):
            self.node.attrs['diffuse'] = 0
        self.node.attrs['diffuse'].locked = False

    def testKeyable(self):
        mc.setAttr('lambert1.colorR', keyable=True)
        self.assertTrue(self.node.attrs['colorR'].keyable)
        self.node.attrs['colorR'].keyable = False
        self.assertFalse(self.node.attrs['colorR'].keyable)
        self.node.attrs['colorR'].keyable = True

    def testConnections(self):
        self.assertIn('initialShadingGroup.surfaceShader', self.node.connections)
        self.assertIn('initialShadingGroup.surfaceShader', self.node.attrs['outColor'].connections)
        self.assertEqual(self.node.attrs['colorR'].connections, [])

        self.assertIn(Node('initialShadingGroup').attrs['surfaceShader'], self.node.attrs['outColor'].connections)
        self.assertNotIn(self.node.attrs['outColor'], self.node.attrs['outColor'].connections)
        self.assertIn(self.node.attrs['outColor'].connections[0], self.node.attrs['outColor'].connections)

    def testConnect(self):
        cube1 = Node(mc.polyCube(name='connectionTest1')[0])
        cube2 = Node(mc.polyCube(name='connectionTest2')[0])
        self.assertNotIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        cube1.attrs['tx'] >> cube2.attrs['tx']
        self.assertIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        cube1.attrs['tx'] // cube2.attrs['tx']
        self.assertNotIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertTrue(cube1.attrs['tx'].connect(cube2.attrs['tx']))
        connection = cube2.attrs['tx'].connections[0]
        self.assertTrue(connection)
        self.assertTrue(connection.disconnect())
        self.assertTrue(connection.connect())
        self.assertTrue(cube1.attrs['tx'].disconnect(cube2.attrs['tx']))
        mc.delete(cube1, cube2)

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

    def testInvalidConnections(self):
        # FATAL ERROR WARNING: Fixed now, but previously this crashed maya
        t1 = Node(mc.createNode('transform', name='connectionDeleteTest1'))
        t2 = Node(mc.createNode('transform', name='connectionDeleteTest2'))
        t2.attrs.create('test', 1)
        attr = t2.attrs['test']

        t1.attrs['tx'] >> t2.attrs['tx']
        attr >> t1.attrs['tx']

        connections = t1.connections
        self.assertEqual(len(connections), 2)
        mc.deleteAttr(t2.attrs['test'])

        self.assertEqual(len(t2.attrs['test'].connections), 0)
        self.assertEqual(len(connections), 2)

        for connection in connections:
            self.assertTrue(connection.name)

        with self.assertRaises(exceptions.AttributeNotFoundError):
            t2.attrs['test'] >> t1.attrs['tx']
        with self.assertRaises(exceptions.AttributeNotFoundError):
            attr >> t1.attrs['tx']

        self.assertEqual(len(connections.connect()), 0)
        self.assertEqual(len(connections.disconnect()), 1)
        self.assertEqual(len(connections.connect()), 1)

        mc.delete(t2)
        for connection in connections:
            self.assertTrue(connection.name)

        with self.assertRaises(exceptions.NodeDeletedError):
            t2.attrs['test'] >> t1.attrs['tx']
        with self.assertRaises(exceptions.AttributeNotFoundError):
            attr >> t1.attrs['tx']

        self.assertEqual(len(connections.connect()), 0)
        self.assertEqual(len(connections.disconnect()), 0)

        mc.delete(t1)


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


class TestUVSets(unittest.TestCase):
    def setUp(self):
        self.node = Node(mc.polyCube(name='uvSetTest')[0]).shape
        mc.polyUVSet(self.node, create=True, uvSet='map2')
        mc.polyUVSet(self.node, currentUVSet=True, uvSet='map1')

    def tearDown(self):
        mc.delete(self.node.parent)

    def testExists(self):
        self.assertEqual(self.node.uvSet, 'map1')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testRename(self):
        self.node.uvSet.name = 'renamed'
        self.assertEqual(self.node.uvSet, 'renamed')
        self.assertEqual(self.node.uvSets, ['renamed', 'map2'])

    def testSet(self):
        self.node.uvSet = 'map2'
        self.assertEqual(self.node.uvSet, 'map2')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testCreate(self):
        with self.assertRaises(exceptions.UVSetNotFoundError):
            self.node.uvSet = 'map3'
        self.assertEqual(self.node.uvSet, 'map1')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testDelete(self):
        with self.assertRaises(exceptions.UVSetDeleteDefaultError):
            self.node.uvSet.delete()
        self.node.uvSet = 'map2'
        self.node.uvSet.delete()
        self.assertEqual(self.node.uvSet, 'map1')
        self.assertEqual(self.node.uvSets, ['map1'])


class TestColorSets(unittest.TestCase):
    def setUp(self):
        self.node = Node(mc.polyCube(name='colorSetTest')[0]).shape
        mc.polyColorSet(self.node, create=True, colorSet='colorSet1')
        mc.polyColorSet(self.node, create=True, colorSet='colorSet2')
        mc.polyColorSet(self.node, currentColorSet=True, colorSet='colorSet1')

    def tearDown(self):
        mc.delete(self.node.parent)

    def testExists(self):
        self.assertEqual(self.node.colorSet, 'colorSet1')
        self.assertEqual(self.node.colorSets, ['colorSet1', 'colorSet2'])

    def testRename(self):
        self.node.colorSet.name = 'renamed'
        self.assertEqual(self.node.colorSet, 'renamed')
        self.assertEqual(self.node.colorSets, ['renamed', 'colorSet2'])

    def testSet(self):
        self.node.colorSet = 'colorSet2'
        self.assertEqual(self.node.colorSet, 'colorSet2')
        self.assertEqual(self.node.colorSets, ['colorSet1', 'colorSet2'])

    def testCreate(self):
        with self.assertRaises(exceptions.ColorSetNotFoundError):
            self.node.colorSet = 'colorSet3'
        self.assertEqual(self.node.colorSet, 'colorSet1')
        self.assertEqual(self.node.colorSets, ['colorSet1', 'colorSet2'])

    def testDelete(self):
        self.node.colorSet.delete()
        self.assertEqual(self.node.colorSet, 'colorSet2')
        self.assertEqual(self.node.colorSets, ['colorSet2'])


if __name__ == '__main__':
    unittest.main()

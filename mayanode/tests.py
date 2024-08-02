import unittest

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from mayanode import Node, Namespace, ProgressBar, exceptions


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

        class StrLikeCls(object):
            def __str__(self): return 'renamedNode'
        node.name = StrLikeCls()
        self.assertEqual(node.name, 'renamedNode')

        mc.delete(node.name)

    def testRenameLocked(self):
        with self.assertRaises(exceptions.RenameReadOnlyNodeError):
            Node('persp').name = 'persp2'

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
        self.assertEqual(len(child.ancestors), 2)
        self.assertFalse(root.ancestors)
        self.assertIn(root, child.ancestors)

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
        self.assertEqual(len(ancestors), 3)

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

        cube = mc.polyCube(name='descendentTest1')[0]
        cube2 = Node(cube).instance(name='descendentTest2')
        group = mc.group(cube, cube2, name='descendentTest3')
        group2 = Node(group).instance(name='descendentTest4')
        overall = mc.group(group, group2, name='descendentTest5')
        self.assertEqual(len(Node(overall).descendents), len(mc.listRelatives(overall, allDescendents=True)))
        mc.delete(cube, cube2, group, group2, overall)

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
        cube = mc.polyCube(name='instTest')[0]
        node = Node(cube)
        shape = node.shape
        self.assertFalse(node.instanced)
        self.assertFalse(shape.instanced)
        inst = node.instance(name='newInst')
        self.assertFalse(node.instanced)
        self.assertTrue(shape.instanced)
        self.assertFalse(inst.instanced)
        self.assertTrue(inst.shape.instanced)
        self.assertEqual(node.name, cube)
        self.assertNotEqual(inst.name, cube)
        mc.delete(node, inst)

    def testInstanceChildren(self):
        cube = mc.polyCube(name='instChildTest1')[0]
        node = Node(cube)
        inst = node.instance(name='instChildTest2')
        self.assertEqual(node.children, [str(node.shape)])
        self.assertNotEqual(inst.children, [str(node.shape)])
        self.assertEqual(inst.children, [str(inst.shape)])
        mc.delete(node, inst)

    def testInstanceHash(self):
        cube = mc.polyCube(name='instHashTest')[0]
        node = Node(cube)
        self.assertEqual(node.instances, [cube])
        inst = node.instance()
        self.assertEqual(node.shape, inst.shape)
        self.assertIsNot(node.shape, inst.shape)
        self.assertEqual(len({node.shape, inst.shape}), 2)
        mc.delete(node, inst)

    def testInstanceList(self):
        cube = mc.polyCube(name='instListTest')[0]
        node = Node(cube)
        shape = node.shape

        self.assertEqual(node.instances, [cube])
        self.assertEqual(shape.instances, [shape.name])

        inst = node.instance()
        self.assertEqual(node.instances, [cube])
        self.assertEqual(shape.instances, [shape.name, inst.shape.name])
        self.assertNotEqual(shape.instances, [inst.shape.name, shape.name])

        instShape = inst.shape
        instA, instB = instShape.instances
        self.assertEqual(instShape, instA)
        self.assertEqual(instShape, instB)

        mc.delete(node)
        self.assertEqual(inst.shape.instances, [inst.shape])
        mc.delete(inst)

    def testInstanceNonDag(self):
        node = Node('time1')
        self.assertEqual(node.name, 'time1')
        self.assertEqual(node.instances, ['time1'])

    def testInstanceDelete(self):
        node = Node(mc.polyCube(name='instDeleteTest')[0])
        inst = node.instance()
        shape = node.shape
        self.assertEqual(shape.instances, [node.shape.name, inst.shape.name])
        mc.delete(shape)
        self.assertFalse(shape.instances)
        mc.delete(node, inst)

    def testInstanceNum(self):
        cube = mc.polyCube(name='instNumTest')[0]
        node = Node(cube)
        shape = node.shape.name
        insts = [node.instance() for _ in range(5)]
        self.assertEqual([inst.shape.api.dagPath.instanceNumber() for inst in insts], [1, 2, 3, 4, 5])
        self.assertEqual(Node(shape, _instanceNumber=5), insts[-1].shape.name)
        self.assertNotEqual(Node(shape, _instanceNumber=5), insts[0].shape.name)
        mc.delete(node)
        mc.delete(insts)

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

    def testShadingGroup(self):
        node = Node(mc.polyCube(name='shadingGroupTest')[0])
        self.assertEqual(node.shadingGroup, None)
        self.assertEqual(node.shape.shadingGroup, 'initialShadingGroup')

        material = mc.shadingNode('lambert', asShader=True)
        sg = mc.sets(empty=True, renderable=True, noSurfaceShader=True)
        mc.connectAttr(material + '.outColor', sg + '.surfaceShader')

        node.shadingGroup = sg
        self.assertEqual(node.shadingGroup, None)
        self.assertEqual(node.shape.shadingGroup, sg)

        node.shape.shadingGroup = 'initialShadingGroup'
        self.assertEqual(node.shadingGroup, None)
        self.assertEqual(node.shape.shadingGroup, 'initialShadingGroup')

        mc.delete(sg, material, node.name)

    def testShadingGroupInst(self):
        node = Node(mc.polyCube(name='shadingGroupInstTest')[0])
        inst = node.instance()

        self.assertEqual(node.shadingGroup, None)
        self.assertEqual(node.shape.shadingGroup, 'initialShadingGroup')
        self.assertEqual(node.shape.shadingGroups, ['initialShadingGroup', 'initialShadingGroup'])

        sg = mc.sets(name='shadingGroupInstTestSG', renderable=True, noSurfaceShader=True, empty=True)
        node.shape.shadingGroup = sg

        self.assertEqual(node.shadingGroup, None)
        self.assertEqual(node.shape.shadingGroup, sg)
        self.assertEqual(inst.shape.shadingGroup, 'initialShadingGroup')
        self.assertEqual(node.shape.shadingGroups, [sg, 'initialShadingGroup'])
        self.assertEqual(inst.shape.shadingGroups, [sg, 'initialShadingGroup'])

        mc.delete(node, inst, sg)

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

    def testMatrix(self):
        node = Node(mc.polyCube(name='matrixTest1')[0])
        node.translate(1.531, -6.42, 3.134)
        node.rotate(35.1, 75.1, -45.953)
        node.scale(1.52, 3.5, -6.3)
        group1 = Node(mc.group(node, name='matrixTest2'))
        group1.translate(13.5, -53.953, 1.95)
        group1.rotate(0.03, -0.135, 53.39853)
        group1.scale(0.31, 0.68, 0.41)
        group2 = Node(mc.group(group1, name='matrixTest3'))
        group2.translate(-5.13, 60.531, -5.1)
        self.assertEqual(node.matrix, mc.xform(node, query=True, matrix=True, worldSpace=True))
        mc.delete(group2)

    def testNamespace(self):
        node = Node(mc.polyCube(name='namespaceTest')[0])
        self.assertEqual(node.namespace, '')

        node.namespace = 'new:namespace'
        self.assertEqual(node.namespace, 'new:namespace')
        self.assertEqual(node.name, 'new:namespace:namespaceTest')
        self.assertEqual(node.longName, '|new:namespace:namespaceTest')

        self.assertIn('namespaceTest', node.namespace.nodes)
        self.assertIn('new:namespace:namespaceTest', node.namespace.nodes)
        self.assertIn('|new:namespace:namespaceTest', node.namespace.nodes)

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
            node.shadingGroup = 'test'
        self.assertIsNone(node.shadingGroup)

    def testDeletedApi(self):
        node = Node(mc.polyCube(name='deleteTest')[0])
        mc.delete(node)

        self.assertIsNotNone(node.api.dependencyNode)
        self.assertIsNotNone(node.api.dagPath)
        self.assertIsNone(node.api.dagNode)

        mc.undo()

        self.assertIsNotNone(node.api.dependencyNode)
        self.assertIsNotNone(node.api.dagPath)
        self.assertIsNotNone(node.api.dagNode)

        mc.delete(node)

        self.assertIsNotNone(node.api.dependencyNode)
        self.assertIsNotNone(node.api.dagPath)
        self.assertIsNotNone(node.api.dagNode)

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

    def testNumVertices(self):
        node = Node(mc.polyCube(name='verticesTest')[0])
        self.assertIsNotNone(node.api.mesh)
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

    def testConstructionHistory(self):
        transform, polyCube = mc.polyCube(name='constructionHistoryTest')
        node = Node(transform)
        smoothNode = mc.polySmooth(node)[0]
        reduceNode = mc.polyReduce(node)[0]
        self.assertEqual(len(node.constructionHistory), 0)

        self.assertEqual(len(node.shape.constructionHistory), 3)
        self.assertEqual(node.shape.constructionHistory[0], reduceNode)

        shapeHistory = node.shape.constructionHistory
        self.assertEqual(shapeHistory[1], smoothNode)
        self.assertEqual(shapeHistory, [reduceNode, smoothNode, polyCube])
        self.assertEqual(Node(smoothNode).constructionHistory.future, [reduceNode, node.shape])

        mc.delete(transform)

    def testTexelDensity(self):
        node = Node(mc.polyPlane(name='texelDensityTest')[0])
        shape = node.shape
        self.assertEqual(shape.texelDensity, 1.0)
        node.texelDensity = 2
        self.assertEqual(round(shape.texelDensity, 1), 2.0)
        shape.texelDensity = 0.5
        self.assertEqual(round(node.texelDensity, 1), 0.5)
        shape.texelDensity = 0
        self.assertEqual(shape.texelDensity, 0.0)
        with self.assertRaises(exceptions.ZeroTexelDensityError):
            shape.texelDensity = 1
        mc.delete(node)

    def testLs(self):
        cube = Node(mc.polyCube(name='lsTest')[0])
        insts = [cube.instance() for _ in range(3)]
        cube2 = Node(mc.polyCube(name='lsTest')[0])
        cube2.parent = cube
        insts[-1].parent = insts[0]
        manip = mc.createNode('translateManip')

        nodeLs = lambda **kwargs: set(node.longName for node in Node.ls(**kwargs))
        mcLs = lambda **kwargs: set(mc.ls(long=True, **kwargs))

        self.assertEqual(nodeLs(), mcLs())
        self.assertEqual(nodeLs(type='transform'), mcLs(type='transform'))
        self.assertEqual(nodeLs(type='mesh'), mcLs(type='mesh'))
        self.assertEqual(nodeLs(type='mesh', allPaths=True), mcLs(type='mesh', allPaths=True))
        self.assertEqual(nodeLs(type='animCurve'), mcLs(type='animCurve'))
        self.assertEqual(nodeLs(assemblies=True), mcLs(assemblies=True))
        self.assertEqual(nodeLs(assemblies=True, type='objectSet'), mcLs(assemblies=True, type='objectSet'))
        self.assertEqual(nodeLs(assemblies=True, type='doesntexist'), mcLs(assemblies=True, type='doesntexist'))

        mc.undo()  # Only way to delete manip
        mc.delete(cube, cube2)
        mc.delete(insts)

    def testLsExactType(self):
        cube = mc.polyCube()[0]
        objSet = mc.sets(name='lsTypeTestObj', empty=True)
        mc.sets(cube, add=objSet)
        edges = ['{}.e[{}]'.format(cube, i) for i in range(4)]
        creaseSet = mc.createNode('creaseSet', name='lsTypeTestCrease')
        mc.sets(edges, add=creaseSet)

        lsObjType = Node.ls(type='objectSet')
        lsObjExactType = Node.ls(exactType='objectSet')
        lsCreaseType = Node.ls(type='creaseSet')
        lsCreaseExactType = Node.ls(exactType='creaseSet')

        self.assertIn(objSet, lsObjType)
        self.assertIn(objSet, lsObjExactType)
        self.assertNotIn(objSet, lsCreaseType)
        self.assertNotIn(objSet, lsCreaseExactType)
        self.assertIn(creaseSet, lsObjType)
        self.assertNotIn(creaseSet, lsObjExactType)
        self.assertIn(creaseSet, lsCreaseType)
        self.assertIn(creaseSet, lsCreaseExactType)

        mc.delete(cube, objSet, creaseSet)

    def testSetMembers(self):
        cube1 = mc.polyCube()[0]
        cube2 = mc.polyCube()[0]
        cube2Shape = mc.listRelatives(cube2, shapes=True, fullPath=True)[0]
        inst = mc.instance(cube2)[0]
        instShape = mc.listRelatives(inst, shapes=True, fullPath=True)[0]
        set1 = mc.sets(empty=True)
        set2 = mc.sets(empty=True)
        mc.sets(cube1, edit=True, forceElement=set1)
        mc.sets(cube2Shape, edit=True, forceElement=set1)
        mc.sets(instShape, edit=True, forceElement=set2)
        mc.sets(set2, edit=True, forceElement=set1)
        self.assertIn(cube2Shape, Node(set1).members)
        self.assertIn(cube1, Node(set1).members)
        self.assertIn(set2, Node(set1).members)
        self.assertEqual(Node(set2).members, [instShape])
        self.assertEqual(Node(cube1).members, [])
        mc.delete(cube1, cube2, inst, set1, set2)


class TestDgModifier(unittest.TestCase):
    def setUp(self):
        cube = mc.polyCube(name='dgModifierTest')[0]
        mc.polyUVSet(cube, create=True, uvSet='map2')
        mc.polyUVSet(cube, currentUVSet=True, uvSet='map1')

        self.withoutMod = Node(cube)
        self.dgMod = om2.MDGModifier()
        self.withDgMod = Node(cube, modifier=self.dgMod)
        self.dagMod = om2.MDagModifier()
        self.withDagMod = Node(cube, modifier=self.dagMod)

    def tearDown(self):
        mc.delete(self.withoutMod)

    def testUVSet(self):
        mc.undoInfo(openChunk=True)
        self.withoutMod.shape.uvSet = 'map2'
        mc.undoInfo(openChunk=False)
        self.assertTrue(self.withoutMod.shape.uvSet, 'map2')
        mc.undo()
        self.assertTrue(self.withoutMod.shape.uvSet, 'map1')

        mc.undoInfo(openChunk=True)
        self.withDgMod.shape.uvSet = 'map2'
        mc.undoInfo(openChunk=False)
        self.assertTrue(self.withDgMod.shape.uvSet, 'map2')
        with self.assertRaises(RuntimeError):
            mc.undo()
        self.assertTrue(self.withDgMod.shape.uvSet, 'map2')
        self.dgMod.undoIt()
        self.assertTrue(self.withDgMod.shape.uvSet, 'map1')


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

    def testTypes(self):
        nodes = []

        locator = Node(mc.spaceLocator(name='boundingBoxTestLocator')[0])
        nodes.append((locator, [locator.shape]))

        light = Node(mc.ambientLight(name='bbTestLight'))
        nodes.append((light.parent, [light]))

        camTransform, camShape = mc.camera(name='bbTestCamera')
        nodes.append((Node(camTransform), [Node(camShape)]))

        plane = Node(mc.plane(name='bbTestPlane'))
        nodes.append((plane, [plane.shape]))

        geo = Node(mc.polyTorus(name='bbTestGeo')[0])
        nodes.append((geo, [geo.shape]))

        inst = geo.instance(name='bbTestInstance')
        nodes.append((inst, [inst.shape]))

        nurbs = Node(mc.nurbsSquare(name='bbTestNurbs')[0])
        nodes.append((nurbs, [nurbs.children[0], nurbs.children[0].shape]))

        volume = Node(mc.createNode('renderCone', name='bbTestVolume'))
        nodes.append((volume.parent, [volume]))

        group = Node(mc.group(geo.duplicate(), plane.duplicate(), name='bbTestGroup'))
        nodes.append((group, [group.children[0], group.children[1].shape]))

        for i, (transform, shapes) in enumerate(nodes):
            transform.attrs['translate'] = [i + 5.13] * 3
            transform.attrs['rotate'] = [i + 72.6] * 3
            transform.attrs['scale'] = [i + 0.53] * 3
            self.assertEqual(transform.boundingBox, tuple(mc.exactWorldBoundingBox(transform)))
            for shape in shapes:
                self.assertEqual(shape.boundingBox, tuple(mc.exactWorldBoundingBox(shape)))
            mc.delete(transform)

        # Doesn't fully work with more complex nurbs curves
        # The CV positions are outside the shape, which is what the API reads
        curve = Node(mc.circle()[0])
        self.assertEqual(curve.boundingBox, curve.shape.boundingBox)
        self.assertNotEqual(curve.boundingBox, tuple(mc.exactWorldBoundingBox(curve)))
        mc.delete(curve)


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

    def testExistsCompound(self):
        cube = mc.polyCube(name='compoundExistsTest')[0]
        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[0].testA', 1)
        mc.setAttr(cube + '.test[1].testA', 1)

        node = Node(cube)
        attr = node.attrs['test']
        element = attr.children[0]
        child = element.children['testA']

        self.assertTrue(child.exists)
        self.assertTrue(element.exists)
        self.assertTrue(attr.exists)

        mc.removeMultiInstance(cube + '.test[0]')

        self.assertFalse(child.exists)
        self.assertFalse(element.exists)
        self.assertTrue(attr.exists)

        mc.deleteAttr(cube + '.test')
        self.assertFalse(child.exists)
        self.assertFalse(element.exists)
        self.assertFalse(attr.exists)

        mc.delete(cube)

    def testEquality(self):
        node1 = Node(mc.polyCube(name='attrLongNameTest1')[0])
        group1 = mc.group(node1, name='attrNameTest1')
        node2 = Node(mc.polyCube(name='attrLongNameTest1')[0])
        group2 = mc.group(node2, name='attrNameTest2')
        attr1 = node1.attrs['translateX']
        attr2 = node2.attrs['translateX']
        self.assertEqual(attr1.api.plug.name(), attr2.api.plug.name())
        self.assertNotEqual(attr1.name, attr2.name)
        self.assertNotEqual(attr1, attr2)

        self.assertEqual(attr1, node1.attrs['tx'])
        self.assertEqual(attr1, node1.attrs['translate'].children['translateX'])
        self.assertEqual(attr1, node1 + '.tx')
        self.assertEqual(attr1, node1 + '.t.tx')
        self.assertEqual(attr1, node1.longName + '.tx')
        self.assertEqual(attr1, node1.longName + '.t.tx')
        self.assertNotEqual(attr1, node2.attrs['tx'])
        self.assertNotEqual(attr1, node2.attrs['translate'].children['translateX'])
        self.assertNotEqual(attr1, node2 + '.tx')
        self.assertNotEqual(attr1, node2 + '.t.tx')

        mc.delete(group1, group2)

    def testCompoundIndex(self):
        cube = mc.polyCube(name='compoundExistsTest')[0]

        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[2].testA', 2)
        mc.setAttr(cube + '.test[0].testA', 0)
        mc.setAttr(cube + '.test[1].testA', 1)
        mc.removeMultiInstance(cube + '.test[0]')

        attr = Node(cube).attrs['test']
        self.assertEqual(list(attr.children.keys()), [1, 2])
        with self.assertRaises(KeyError):
            attr.children[0]
        element = attr.children[2]
        self.assertEqual(list(element.children.keys()), ['testA'])
        child = element.children['testA']
        self.assertFalse(child.children)
        self.assertEqual(child.value, 2.0)

        mc.delete(cube)

    def testDefaultGet(self):
        self.assertIsNotNone(self.node.attrs.get('diffuse'))
        self.assertIsNone(self.node.attrs.get('something'))

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
        cube1 = Node(mc.polyCube(name='connectionTest')[0])
        cube2 = Node(mc.polyCube(name='connectionTest')[0])
        self.assertFalse(cube1.connections)
        self.assertFalse(cube1.attrs['tx'].connections)
        self.assertNotIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertTrue(cube1.attrs['tx'] >> cube2.attrs['tx'])
        self.assertTrue(cube1.connections)
        self.assertTrue(cube1.attrs['tx'].connections)
        self.assertIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertTrue(cube1.attrs['tx'] // cube2.attrs['tx'])
        self.assertNotIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertTrue(cube1.attrs['tx'].connect(cube2.attrs['tx']))
        connection = cube2.attrs['tx'].connections[0]
        self.assertTrue(connection)
        self.assertTrue(connection.disconnect())
        self.assertFalse(connection)
        self.assertTrue(connection.connect())
        self.assertTrue(cube1.attrs['tx'].disconnect(cube2.attrs['tx']))
        mc.delete(cube1, cube2)

    def testConnectReverse(self):
        cube1 = Node(mc.polyCube(name='connectionTest3')[0])
        cube2 = Node(mc.polyCube(name='connectionTest4')[0])
        cube2.attrs['tx'] >> cube1.attrs['tx']
        self.assertIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertIn(cube2.attrs['tx'], cube1.attrs['tx'].connections)
        self.assertFalse(cube1.attrs['tx'] // cube2.attrs['tx'])
        self.assertTrue(cube2.attrs['tx'] // cube1.attrs['tx'])
        self.assertNotIn(cube1.attrs['tx'], cube2.attrs['tx'].connections)
        self.assertTrue(cube2.attrs['tx'].connect(cube1.attrs['tx']))
        connection = cube1.attrs['tx'].connections[0]
        self.assertTrue(connection)
        self.assertTrue(connection.disconnect())
        self.assertFalse(connection)
        self.assertTrue(connection.connect())
        self.assertTrue(cube2.attrs['tx'].disconnect(cube1.attrs['tx']))
        mc.delete(cube1, cube2)

    def testConnectionInvalid(self):
        cube1 = Node(mc.polyCube(name='connectionTest')[0])
        with self.assertRaises(exceptions.ConnectToSelfError):
            cube1.attrs['tx'] >> cube1.attrs['tx']
        mc.delete(cube1)

    def testConnectChildren(self):
        cubeA = Node(mc.polyCube(name='connectionTest')[0]).shape
        cubeB = Node(mc.polyCube(name='connectionTest')[0]).shape
        existingConsA = list(cubeA.connections)
        uvSetA = cubeA.attrs['uvSet']
        uvSetB = cubeB.attrs['uvSet']
        uvSetA >> uvSetB
        uvSetA1 = uvSetA.children[0]
        uvSetB1 = uvSetB.children[0]
        uvSetA1 >> uvSetB1
        uvSetA1Name = uvSetA1.children['uvSetName']
        uvSetB1Name = uvSetB1.children['uvSetName']
        uvSetA1Name >> uvSetB1Name

        self.assertTrue(cubeA.connections)
        self.assertEqual(len([con for con in cubeA.connections if con not in existingConsA]), 3)
        self.assertTrue(uvSetA.connections)
        self.assertEqual(len(uvSetA.connections), 3)
        self.assertTrue(uvSetA1.connections)
        self.assertEqual(len(uvSetA1.connections), 2)
        self.assertTrue(uvSetA1Name.connections)
        self.assertEqual(len(uvSetA1Name.connections), 1)

        uvSetA // uvSetB
        uvSetA1 // uvSetB1

        self.assertTrue(cubeA.connections)
        self.assertEqual(len([con for con in cubeA.connections if con not in existingConsA]), 1)
        self.assertTrue(uvSetA.connections)
        self.assertEqual(len(uvSetA.connections), 1)
        self.assertTrue(uvSetA1.connections)
        self.assertEqual(len(uvSetA1.connections), 1)
        self.assertTrue(uvSetA1Name.connections)
        self.assertEqual(len(uvSetA1Name.connections), 1)

        uvSetA1Name // uvSetB1Name

        self.assertTrue(cubeA.connections)
        self.assertEqual(len([con for con in cubeA.connections if con not in existingConsA]), 0)
        self.assertFalse(uvSetA.connections)
        self.assertEqual(len(uvSetA.connections), 0)
        self.assertFalse(uvSetA1.connections)
        self.assertEqual(len(uvSetA1.connections), 0)
        self.assertFalse(uvSetA1Name.connections)
        self.assertEqual(len(uvSetA1Name.connections), 0)

        mc.delete(cubeA.parent, cubeB.parent)

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

    def testDelete(self):
        cube = mc.polyCube(name='compoundExistsTest')[0]
        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[0].testA', 1)
        mc.setAttr(cube + '.test[1].testA', 1)

        node = Node(cube)
        attr = node.attrs['test']
        element = attr.children[0]
        child = element.children['testA']

        with self.assertRaises(RuntimeError):
            child.delete()
        element.delete()
        self.assertEqual(list(attr.children.keys()), [1])
        attr.delete()
        self.assertNotIn('test', Node(cube).attrs)
        self.assertFalse(node.attrs['test'].exists)
        with self.assertRaises(exceptions.AttributeNotFoundError):
            attr.children
        mc.delete(cube)

    def testCreateFromDelete(self):
        cube = mc.polyCube(name='compoundExistsTest')[0]

        mc.addAttr(cube, longName='test', attributeType='long')
        attr = Node(cube).attrs['test']
        attr.value = 5
        attr.delete()
        attr.create()
        self.assertIs(attr.type, int)
        self.assertEqual(attr.value, 0)
        attr.delete()

        mc.delete(cube)

    def testCreateFromDeleteUnknownType(self):
        cube = mc.polyCube(name='compoundExistsTest')[0]

        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[0].testA', 1)
        mc.setAttr(cube + '.test[1].testA', 1)
        attr = Node(cube).attrs['test']
        attr.delete()
        attr.create()
        self.assertIs(attr.type, float)  # Falls back to default with a non standard type
        attr.delete()
        attr.create(attributeType='bool')
        self.assertIs(attr.type, bool)

        mc.delete(cube)

    def testChildrenPlugElement(self):
        attr = Node('renderLayerManager').attrs['renderLayerId']
        self.assertEqual(len(attr.children), 1)
        self.assertEqual(attr.children[0], 'renderLayerId[0]')
        self.assertEqual(attr.children[0], 'renderLayerManager.renderLayerId[0]')
        with self.assertRaises(KeyError):
            attr.children[1]
        self.assertEqual(attr.children[0].connections[0].attr, 'defaultRenderLayer.identification')

    def testChildrenPlugChild(self):
        attr = Node('persp').attrs['translate']
        self.assertEqual(len(attr.children), 3)
        self.assertEqual(attr.children[0], 'translateX')
        self.assertEqual(attr.children[0], 'translate.translateX')
        self.assertEqual(attr.children[0], 'persp.translate.translateX')
        self.assertEqual(attr.children[0], 'persp.translateX')
        self.assertEqual(attr.children[0], 'persp.t.tx')
        self.assertEqual(attr.children[0], 'persp.tx')
        self.assertNotEqual(attr.children[0], 'persp.translate.tx')
        self.assertEqual(attr.children['translateY'], 'translateY')
        with self.assertRaises(KeyError):
            attr.children['ty']

    def testChildrenPlugCompound(self):
        cube = mc.polyCube(name='compoundChildTest')[0]

        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[2].testA', 2)
        mc.setAttr(cube + '.test[0].testA', 0)
        mc.setAttr(cube + '.test[1].testA', 1)

        attr = Node(cube).attrs['test']
        self.assertEqual(len(attr.children), 3)
        self.assertEqual(attr.children[1], 'test[1]')
        self.assertEqual(attr.children[1].children[0], attr.children[1].children['testA'])
        self.assertEqual(attr.children[1].children[0], cube + '.test[1].testA')
        self.assertEqual(attr.children[1].children[0], 'test[1].testA')
        self.assertEqual(attr.children[1].children[0], 'testA')

        mc.delete(cube)

    def testConnected(self):
        node = Node(mc.polyCube(name='connectedAttrTest')[0])
        'persp.tx' >> node.attrs['tx']
        with self.assertRaises(exceptions.AttributeConnectedError):
            node.attrs['tx'] = 5
        node.attrs['ty'].keyframes[1].set()
        self.assertTrue(node.attrs['ty'].api.plug.isConnected)
        node.attrs['ty'] = 5
        node.delete()

class TestKeyframes(unittest.TestCase):
    def setUp(self):
        self.node = Node(mc.polyCube(name='keyframeTest')[0])
        for i in range(3):
            mc.setKeyframe(self.node + '.tx', time=(i, i), value=-i)
        mc.setKeyframe(self.node + '.tx', time=(3, 5), value=10)
        mc.setKeyframe(self.node + '.tx', time=(9, 9), value=-5)
        mc.setKeyframe(self.node + '.ty', time=(0, 0), value=0)
        mc.setKeyframe(self.node + '.ty', time=(5, 5), value=-10)
        mc.setKeyframe(self.node + '.ty', time=(10, 10), value=5)

        self.nodeKeyframes = self.node.keyframes
        self.attrKeyframes = self.node.attrs['tx'].keyframes

    def tearDown(self):
        mc.delete(self.node)

    def testAttrGet(self):
        self.assertEqual(self.attrKeyframes.keys(), [0.0, 1.0, 2.0, 3.0, 5.0, 9.0])
        self.assertEqual(self.attrKeyframes.values(), [0.0, -1.0, -2.0, 10.0, 10.0, -5.0])
        self.assertEqual(list(self.attrKeyframes.items()), list(zip(self.attrKeyframes.keys(), self.attrKeyframes.values())))
        self.assertEqual(self.attrKeyframes, {0.0: 0.0, 1.0: -1.0, 2.0: -2.0, 3.0: 10.0, 5.0: 10.0, 9.0: -5.0})

        self.assertEqual(self.attrKeyframes[1].value, -1)
        self.assertEqual(self.attrKeyframes[1.0].value, -1)
        self.assertIsNone(self.attrKeyframes[4].value)

    def testNodeGet(self):
        self.assertEqual(self.nodeKeyframes.keys(), [0.0, 1.0, 2.0, 3.0, 5.0, 9.0, 0.0, 5.0, 10.0])
        self.assertEqual(self.nodeKeyframes.values(), [0.0, -1.0, -2.0, 10.0, 10.0, -5.0, 0.0, -10.0, 5.0])
        self.assertEqual(list(self.nodeKeyframes.items()), list(zip(self.nodeKeyframes.keys(), self.nodeKeyframes.values())))
        self.assertEqual(self.nodeKeyframes, {0.0: 0.0, 1.0: -1.0, 2.0: -2.0, 3.0: 10.0, 5.0: -10.0, 9.0: -5.0, 10.0: 5.0})

    def testGetSlice(self):
        self.assertEqual(self.attrKeyframes[1:3].value, [-1.0, -2.0])
        self.assertEqual(self.attrKeyframes[1:6:2].value, [-1.0, 10.0, 10.0])
        self.assertEqual(self.nodeKeyframes[1:3].value, [-1.0, -2.0])
        self.assertEqual(self.nodeKeyframes[1:6:2].value, [-1.0, 10.0, 10.0, -10.0])

    def testSetValue(self):
        self.attrKeyframes[2] = 10
        self.attrKeyframes[3].set(20)
        self.assertEqual(self.attrKeyframes[1].value, -1)
        self.assertEqual(self.attrKeyframes[2].value, 10)
        self.assertEqual(self.attrKeyframes[3].value, 20)
        self.assertIsNone(self.attrKeyframes[4].value)

        self.nodeKeyframes[8] = 50
        self.assertEqual(self.attrKeyframes[8].value, 50)

    def testSetCurrent(self):
        self.assertNotIn(7, mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))
        self.attrKeyframes[7] = None
        self.assertIn(7, mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))
        self.assertTrue(-5 < mc.keyframe(self.node, attribute='tx', query=True, valueChange=True, time=(7, 7))[0] < 10)

        self.assertNotIn(7, mc.keyframe(self.node, attribute='ty', query=True, timeChange=True))
        self.nodeKeyframes[7].set(outTangentType='step')
        self.assertIn(7, mc.keyframe(self.node, attribute='ty', query=True, timeChange=True))
        self.assertTrue(-10 < mc.keyframe(self.node, attribute='ty', query=True, valueChange=True, time=(7, 7))[0] < 5)

        del self.nodeKeyframes[7]

    def testDelete(self):
        self.assertEqual(self.attrKeyframes[1].value, -1)
        del self.attrKeyframes[1]
        self.assertIsNone(self.attrKeyframes[1].value)

        self.assertEqual(self.attrKeyframes[5].value, 10)
        self.attrKeyframes[5].delete()
        self.assertIsNone(self.attrKeyframes[5].value)

        self.assertIn(0, mc.keyframe(self.node, attribute='ty', query=True, timeChange=True))
        del self.nodeKeyframes[0]
        self.assertNotIn(0, mc.keyframe(self.node, attribute='ty', query=True, timeChange=True))

        self.assertIn(2, mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))
        self.nodeKeyframes[2].delete()
        self.assertNotIn(2, mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))

        self.assertTrue(mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))
        self.attrKeyframes.delete()
        self.assertFalse(mc.keyframe(self.node, attribute='tx', query=True, timeChange=True))

        self.assertTrue(mc.keyframe(self.node, query=True, timeChange=True))
        self.nodeKeyframes.delete()
        self.assertFalse(mc.keyframe(self.node, query=True, timeChange=True))


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

    def testLength(self):
        self.assertTrue(self.node.uvSets)
        self.assertEqual(len(self.node.uvSets), 2)

    def testRename(self):
        self.node.uvSet.name = 'renamed'
        self.assertEqual(self.node.uvSet, 'renamed')
        self.assertEqual(self.node.uvSets, ['renamed', 'map2'])

    def testSet(self):
        self.node.uvSet = 'map2'
        self.assertEqual(self.node.uvSet, 'map2')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testSetInvalid(self):
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

    def testFaces(self):
        for face in self.node.faces:
            self.assertEqual(len(face.uvSets), 2)

    def testCreate(self):
        original = list(self.node.uvSets)
        uvSets = self.node.uvSets
        uvSet = uvSets.create('NewUVSet')
        self.assertIn(uvSet, self.node.uvSets)
        self.assertIn(uvSet, uvSets)
        self.assertEqual(self.node.uvSets, original + [uvSet])
        self.assertEqual(self.node.uvSet, self.node.uvSets[0])

    def testIndex(self):
        uvSet1 = self.node.uvSets.create('NewUVSet1')
        uvSet2 = self.node.uvSets.create('NewUVSet2')
        uvSet1.delete()
        uvSet3 = self.node.uvSets.create('NewUVSet2')

        self.assertEqual(self.node.uvSets, ['map1', 'map2', uvSet2, uvSet3])
        self.assertEqual(len(self.node.attrs['uvSet']), 5)

        with self.assertRaises(exceptions.UVSetNotFoundError):
            uvSet1.physicalIndex
        with self.assertRaises(exceptions.UVSetNotFoundError):
            uvSet1.logicalIndex

        self.assertEqual(uvSet2.physicalIndex, 2)
        self.assertEqual(uvSet2.logicalIndex, 3)

        self.assertEqual(uvSet3.physicalIndex, 3)
        self.assertEqual(uvSet3.logicalIndex, 4)

        for uvSet in self.node.uvSets:
            idx = uvSet.logicalIndex
            attr = self.node.attrs['uvSet'].children[idx].children['uvSetName']
            self.assertEqual(attr.value, uvSet)
            self.assertEqual(attr, uvSet.attr)

    def testCurrent(self):
        map1, map2 = self.node.uvSets
        self.assertTrue(map1.current)
        self.assertFalse(map2.current)


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


class TestNamespace(unittest.TestCase):
    def setUp(self):
        mc.namespace(set=':')
        self.ns1 = ':' + mc.namespace(add='namespaceTest1')
        self.ns2 = ':' + mc.namespace(add='namespaceTest2', parent=self.ns1)
        self.ns3 = ':' + mc.namespace(add='namespaceTest3', parent=self.ns2)

    def tearDown(self):
        if mc.namespace(exists=self.ns3):
            mc.namespace(removeNamespace=self.ns3)
        if mc.namespace(exists=self.ns2):
            mc.namespace(removeNamespace=self.ns2)
        if mc.namespace(exists=self.ns1):
            mc.namespace(removeNamespace=self.ns1)

    def testExists(self):
        self.assertTrue(Namespace(self.ns1).exists)
        ns3 = str(self.ns3).strip(':')
        self.assertTrue(Namespace(ns3).exists)
        self.assertTrue(Namespace(':' + ns3).exists)
        self.assertFalse(Namespace(ns3.split(':')[-1]).exists)

    def testCreate(self):
        ns4 = Namespace('emptyLevel3')
        self.assertFalse(ns4.exists)
        self.assertTrue(ns4.create())
        self.assertFalse(ns4.create())
        self.assertTrue(ns4.exists)
        self.assertTrue(ns4.delete())
        self.assertFalse(ns4.delete())
        self.assertFalse(ns4.exists)

    def testReparent(self):
        with self.assertRaises(AttributeError):
            Namespace(self.ns3).parent = self.ns1

    def testDelete(self):
        with self.assertRaises(exceptions.NamespaceNotEmptyError):
            Namespace(self.ns2).delete()
        self.assertTrue(Namespace(self.ns3).delete())
        self.assertTrue(Namespace(self.ns2).delete())

    def testParent(self):
        self.assertEqual(Namespace(self.ns3).parent, self.ns2)
        self.assertEqual(Namespace(self.ns1).parent, ':')
        self.assertIsNone(Namespace(':').parent)

    def testChildren(self):
        self.assertIn(self.ns3, Namespace(self.ns2).children)
        self.assertEqual(Namespace(self.ns3).children, [])
        self.assertIn(self.ns1, Namespace().children)

    def testCurrent(self):
        self.assertEqual(Namespace.current, ':')
        ns3 = str(self.ns3).strip(':')
        Namespace.current = ns3
        self.assertEqual(Namespace.current, ns3)
        Namespace.current = ':' + ns3
        self.assertEqual(Namespace.current, ns3)
        with self.assertRaises(exceptions.NamespaceNotFoundError):
            Namespace.current = ns3.split(':')[-1]

    def testRoot(self):
        self.assertEqual(Namespace.root, ':')
        self.assertIn(self.ns1, Namespace.root.children)
        with self.assertRaises(AttributeError):
            Namespace.root = ':'

    def testDepth(self):
        self.assertEqual(Namespace.root.depth, 0)
        self.assertEqual(Namespace(self.ns3).depth, 3)

    def testAncestors(self):
        self.assertEqual(Namespace(self.ns2).ancestors, [self.ns1, ':'])

    def testDescendents(self):
        self.assertEqual(Namespace(self.ns1).descendents, [self.ns2, self.ns3])


class TestProgressBar(unittest.TestCase):
    def setUp(self):
        self.gMainProgressBar = mel.eval('$tmp = $gMainProgressBar;')

    def tearDown(self):
        mc.progressBar(self.gMainProgressBar, edit=True, progress=0, status='',
                       minValue=0, maxValue=100, isInterruptable=False)

    def testLimits(self):
        ProgressBar.min = -1000
        ProgressBar.max = 1000
        self.assertEqual(ProgressBar.limits, (-1000, 1000))
        ProgressBar.limits = (50, 150)
        self.assertEqual(ProgressBar.min, 50)
        self.assertEqual(ProgressBar.max, 150)

        with self.assertRaises(RuntimeError):
            ProgressBar.min = 1000

    def testValue(self):
        ProgressBar.show()
        self.assertEqual(ProgressBar.value, 0)
        ProgressBar.value += 1
        self.assertEqual(ProgressBar.value, 1)
        ProgressBar.step(1)
        self.assertEqual(ProgressBar.value, 2)
        ProgressBar.hide()

    def testWhile(self):
        with ProgressBar:
            while not ProgressBar.interrupted and ProgressBar.value < ProgressBar.max:
                ProgressBar.step(1)

    def testRange(self):
        x = 0
        for i in ProgressBar.range(10):
            self.assertEqual(ProgressBar.value, i)
            x += i
        for i in ProgressBar.range(16, 72):
            self.assertEqual(ProgressBar.value, i)
            x += i
        for i in ProgressBar.range(16, 72, 3):
            self.assertEqual(ProgressBar.value, i)
            x += i
        self.assertEqual(x, sum(range(10)) + sum(range(16, 72)) + sum(range(16, 72, 3)))

    def testEnumerate(self):
        for i, val in ProgressBar.enumerate('abc'):
            self.assertEqual(ProgressBar.value, i)
            self.assertEqual(val, 'abc'[i])

        for i, val in ProgressBar.enumerate('abc', 10):
            self.assertEqual(ProgressBar.value, i)
            self.assertEqual(val, 'abc'[i - 10])

    def testMisc(self):
        with ProgressBar:
            self.assertEqual(ProgressBar.status, '')
            ProgressBar.status = 'test'
            self.assertEqual(ProgressBar.status, 'test')

            self.assertFalse(ProgressBar.interruptable)
            ProgressBar.interruptable = True
            self.assertTrue(ProgressBar.interruptable)
            self.assertFalse(ProgressBar.interrupted)


if __name__ == '__main__':
    unittest.main()

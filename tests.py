import os
import tempfile
import unittest

import maya.api.OpenMaya as om2  # type: ignore
import maya.cmds as mc  # type: ignore
import maya.mel as mel  # type: ignore

from mayanode import *
from mayanode.version import tokeniseVersion, standardiseVersions


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

        node.namespace = 'test:namespace'
        node.parent.namespace = 'test:namespace'
        self.assertEqual(node, 'equalityTest1')
        self.assertEqual(node, 'equalityTest1|')
        self.assertNotEqual(node, '|equalityTest1')
        self.assertNotEqual(node, '|equalityTest1|')
        self.assertNotEqual(node, 'equalityGroup1|equalityTest1')
        self.assertNotEqual(node, '|equalityGroup1|equalityTest1')
        self.assertEqual(node, 'test:namespace:equalityTest1')
        self.assertEqual(node, 'test:namespace:equalityTest1|')
        self.assertNotEqual(node, '|test:namespace:equalityTest1|')
        self.assertEqual(node, 'test:namespace:equalityGroup1|test:namespace:equalityTest1')
        self.assertEqual(node, 'test:namespace:equalityGroup1|test:namespace:equalityTest1|')
        self.assertEqual(node, '|test:namespace:equalityGroup1|test:namespace:equalityTest1')
        self.assertEqual(node, '|test:namespace:equalityGroup1|test:namespace:equalityTest1|')
        self.assertEqual(node, ':test:namespace:equalityGroup1|:test:namespace:equalityTest1')
        self.assertEqual(node, ':test:namespace:equalityGroup1|:test:namespace:equalityTest1|')
        self.assertEqual(node, '|:test:namespace:equalityGroup1|:test:namespace:equalityTest1')
        self.assertEqual(node, '|:test:namespace:equalityGroup1|:test:namespace:equalityTest1|')

        mc.delete(node, node2, node.parent)
        mc.namespace(removeNamespace='test:namespace')
        mc.namespace(removeNamespace='test')

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
        lambert = Node('lambert1')
        self.assertEqual(lambert.type, 'lambert')
        new = Node(mc.createNode('transform', name='nodeTypeTest'))
        self.assertEqual(new.type, 'transform')

        self.assertIn('shadingDependNode', lambert.type.inherited)
        self.assertNotIn('dagNode', lambert.type.inherited)

        self.assertIn('transform', new.type.inherited)
        self.assertIn('dagNode', new.type.inherited)
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
        self.assertEqual(list(node.matrix), mc.xform(node, query=True, matrix=True, worldSpace=True))
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
        self.assertEqual(node.name, 'new:namespace:namespaceTest2')
        self.assertEqual(node.namespace, 'new:namespace')
        self.assertEqual(node.parent.namespace, '')

        node.name = 'new:namespaceTest1'
        self.assertEqual(node.name, 'new:namespaceTest1')
        self.assertEqual(node.namespace, 'new')

        node.name = 'new:namespace2:namespaceTest1'
        self.assertEqual(node.name, 'new:namespace2:namespaceTest1')
        self.assertEqual(node.namespace, 'new:namespace2')

        node.name = ':new:namespace3:namespaceTest1'
        self.assertEqual(node.name, 'new:namespace3:namespaceTest1')
        self.assertEqual(node.namespace, 'new:namespace3')

        node.name = ':namespaceTest2'
        self.assertFalse(node.namespace)

        mc.delete(node.name)
        mc.namespace(removeNamespace='new:namespace')
        mc.namespace(removeNamespace='new:namespace2')
        mc.namespace(removeNamespace='new:namespace3')
        mc.namespace(removeNamespace='new')

    def testDeleted(self):
        node = Node(mc.polyCube(name='deleteTest')[0])
        mc.delete(node)

        with self.assertRaises(exceptions.NodeDeletedError):
            node.name
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
        mc.select('persp', 'perspShape', 'defaultLightSet', insts[-1])

        nodeLs = lambda *args, **kwargs: set(node.longName for node in Node.ls(*args, _api=True, **kwargs))
        mcLs = lambda *args, **kwargs: set(mc.ls(*args, long=True, **kwargs))

        self.assertEqual(nodeLs(), mcLs())
        self.assertEqual(nodeLs('perspShape'), mcLs('perspShape'))
        self.assertEqual(nodeLs('persp|perspShape'), mcLs('persp|perspShape'))
        self.assertEqual(nodeLs('persp|perspShape1'), mcLs('persp|perspShape1'))
        self.assertEqual(nodeLs('*persp*|*Shape*'), mcLs('*persp*|*Shape*'))
        self.assertEqual(nodeLs('persp'), mcLs('persp'))
        self.assertEqual(nodeLs('persp*'), mcLs('persp*'))
        self.assertEqual(nodeLs('persp', 'perspShape'), mcLs('persp', 'perspShape'))
        self.assertEqual(nodeLs(['persp', 'perspShape']), mcLs(['persp', 'perspShape']))
        self.assertEqual(nodeLs('persp*', type='camera'), mcLs('persp*', type='camera'))
        self.assertEqual(nodeLs('persp*', type='transform'), mcLs('persp*', type='transform'))
        self.assertEqual(nodeLs(type='transform'), mcLs(type='transform'))
        self.assertEqual(nodeLs(type='mesh'), mcLs(type='mesh'))
        self.assertEqual(nodeLs(type='transform', allPaths=True), mcLs(type='transform', allPaths=True))
        self.assertEqual(nodeLs(type='mesh', allPaths=True), mcLs(type='mesh', allPaths=True))
        self.assertEqual(nodeLs(allPaths=True), mcLs(allPaths=True))
        self.assertEqual(nodeLs(assemblies=True), mcLs(assemblies=True))
        self.assertEqual(nodeLs(assemblies=True, allPaths=True), mcLs(assemblies=True, allPaths=True))
        self.assertEqual(nodeLs(assemblies=True, type='objectSet'), mcLs(assemblies=True, type='objectSet'))
        self.assertEqual(nodeLs('persp', assemblies=True), mcLs('persp', assemblies=True))
        self.assertEqual(nodeLs('persp*', assemblies=True), mcLs('persp', assemblies=True))
        self.assertEqual(nodeLs('persp', type='camera', assemblies=True), mcLs('persp', type='camera', assemblies=True))
        self.assertEqual(nodeLs('persp*', type='camera', assemblies=True), mcLs('persp*', type='camera', assemblies=True))
        with self.assertRaises(RuntimeError):
            self.assertEqual(nodeLs(type='_invalid'), mcLs(type='_invalid'))
        with self.assertRaises(RuntimeError):
            self.assertEqual(nodeLs('persp', type='_invalid'), mcLs('persp', type='_invalid'))
        with self.assertRaises(RuntimeError):
            self.assertEqual(nodeLs(assemblies=True, type='_invalid'), mcLs(assemblies=True, type='_invalid'))
        self.assertEqual(nodeLs(selection=True), mcLs(selection=True))
        self.assertEqual(nodeLs('persp', selection=True), mcLs('persp', selection=True))
        self.assertEqual(nodeLs('persp*', selection=True), mcLs('persp*', selection=True))
        self.assertEqual(nodeLs('perspShape', selection=True), mcLs('perspShape', selection=True))
        self.assertEqual(nodeLs('persp', selection=True, assemblies=True), mcLs('persp', selection=True, assemblies=True))
        self.assertEqual(nodeLs('persp', selection=True, type='transform'), mcLs('persp', selection=True, type='transform'))
        self.assertEqual(nodeLs('persp', selection=True, assemblies=True, type='transform'), mcLs('persp', selection=True, assemblies=True, type='transform'))
        self.assertEqual(nodeLs('persp', selection=True, assemblies=True, type='mesh'), mcLs('persp', selection=True, assemblies=True, type='mesh'))
        self.assertEqual(nodeLs('perspShape' for _ in range(1)), mcLs('perspShape' for _ in range(1)))

        mc.undo()  # Only way to delete manip
        mc.undo()
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
    def testContext(self):
        dg1 = om2.MDGModifier()
        dg2 = om2.MDGModifier()
        dg3 = om2.MDGModifier()
        dag1 = om2.MDagModifier()
        dag2 = om2.MDagModifier()

        self.assertIsNone(MayaNode.dgModifier)
        MayaNode.dgModifier = dg1
        with MayaNode() as context1:
            self.assertIs(MayaNode.dgModifier, dg1)
            self.assertIsNone(context1.dgModifier)
            context1.dgModifier = dg2
            self.assertIs(MayaNode.dgModifier, dg2)
            self.assertIs(context1.dgModifier, dg2)

            with MayaNode() as context2:
                self.assertIs(MayaNode.dgModifier, dg2)
                context2.dgModifier = dg3
                self.assertIs(context1.dgModifier, dg2)
                self.assertIs(MayaNode.dgModifier, dg3)
                context1.dgModifier = None

            self.assertIs(MayaNode.dgModifier, dg1)
            self.assertIs(MayaNode.modifier, dg1)
            context1.dagModifier = dag1
            self.assertIs(MayaNode.modifier, dag1)

            with MayaNode() as context2:
                context2.dagModifier = dag2
                self.assertIs(MayaNode.modifier, dag2)
                context2.dgModifier = dg3
                self.assertIs(MayaNode.modifier, dag2)
                self.assertIs(context1.modifier, dag1)

        MayaNode.dgModifier = None

    def testUVSet(self):
        node = Node(mc.polyCube(name='uvDgModTest')[0])
        mc.polyUVSet(node, create=True, uvSet='map2')
        mc.polyUVSet(node, currentUVSet=True, uvSet='map1')

        mc.undoInfo(openChunk=True)
        node.shape.uvSet = 'map2'
        mc.undoInfo(openChunk=False)
        self.assertTrue(node.shape.uvSet, 'map2')
        mc.undo()
        self.assertTrue(node.shape.uvSet, 'map1')

        with MayaNode() as context:
            context.dgModifier = om2.MDGModifier()

            mc.undoInfo(openChunk=True)
            node.shape.uvSet = 'map2'
            mc.undoInfo(openChunk=False)
            self.assertTrue(node.shape.uvSet, 'map2')
            with self.assertRaises(RuntimeError):
                mc.undo()
            self.assertTrue(node.shape.uvSet, 'map2')
            context.dgModifier.undoIt()
            self.assertTrue(node.shape.uvSet, 'map1')

        with MayaNode() as context:
            context.dgModifier = om2.MDGModifier()

            self.assertIn('map2', node.shape.uvSets)
            self.assertTrue(node.shape.uvSets['map2'].exists)
            node.shape.uvSets['map2'].delete()
            self.assertNotIn('map2', node.shape.uvSets)
            context.dgModifier.undoIt()
            self.assertIn('map2', node.shape.uvSets)

        with MayaNode() as context:
            context.dgModifier = om2.MDGModifier()

            mc.undoInfo(openChunk=True)
            node.shape.uvSet.name = 'map3'
            mc.undoInfo(openChunk=False)
            self.assertTrue(node.shape.uvSet, 'map3')
            self.assertTrue(node.shape.uvSets, ['map3', 'map2'])
            with self.assertRaises(RuntimeError):
                mc.undo()
            with self.assertRaises(exceptions.UVSetExistsError):
                node.shape.uvSet.name = 'map2'
            context.dgModifier.undoIt()
            self.assertEqual(node.shape.uvSet.name, 'map1')

        mc.delete(node)


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

    def testValueKAny(self):
        surfaceShader =  Node('initialShadingGroup').attrs['surfaceShader']
        outColor = Node('lambert1').attrs['outColor']
        self.assertEqual(surfaceShader.type, (float, float, float))
        self.assertEqual(outColor.type, (float, float, float))
        self.assertEqual(surfaceShader.value, (0, 0, 0))
        self.assertEqual(outColor.value, (0, 0, 0))

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
        self.assertNotIn('test', attrs)
        self.assertIn('color', attrs)

    def testInvalidConnections(self):
        t1 = Node(mc.createNode('transform', name='connectionDeleteTest1'))
        t2 = Node(mc.createNode('transform', name='connectionDeleteTest2'))
        t2.attrs.create('test', 1)
        attr = t2.attrs['test']

        t1.attrs['tx'] >> t2.attrs['tx']
        attr >> t1.attrs['tx']

        connections = t1.connections
        self.assertEqual(len(connections), 2)
        mc.deleteAttr(t2.attrs['test'])

        self.assertEqual(len(attr.connections), 0)
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

        attrStr = str(attr)
        mc.delete(t2)
        for connection in connections:
            with self.assertRaises(exceptions.NodeDeletedError):
                connection.name

        with self.assertRaises(exceptions.NodeDeletedError):
            t2.attrs['test'] >> t1.attrs['tx']
        with self.assertRaises(exceptions.NodeDeletedError):
            attr >> t1.attrs['tx']
        with self.assertRaises(exceptions.NodeNotFoundError):
            attrStr >> t1.attrs['tx']

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
        attrs = node.attrs
        attr = attrs['test']
        element = attr.children[0]
        child = element.children['testA']

        self.assertIn('test', attrs)
        self.assertIn('test', node.attrs)
        with self.assertRaises(RuntimeError):
            child.delete()
        element.delete()
        self.assertEqual(list(attr.children.keys()), [1])
        attr.delete()
        self.assertNotIn('test', node.attrs)
        self.assertIn('test', attrs)
        self.assertFalse(attr.exists)
        self.assertFalse(attrs['test'].exists)
        with self.assertRaises(exceptions.AttributeNotFoundError):
            node.attrs['test']
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
        self.assertEqual(attr.children['ty'], 'translateY')
        self.assertEqual(attr.children['translateY'], 'ty')
        self.assertEqual(attr.children['ty'], 'ty')

    def testChildrenPlugCompound(self):
        cube = mc.polyCube(name='compoundChildTest')[0]

        mc.addAttr(cube, longName='test', attributeType='compound', numberOfChildren=1, multi=True)
        mc.addAttr(cube, longName='testA', attributeType='float', parent='test')
        mc.setAttr(cube + '.test[2].testA', 2)
        mc.setAttr(cube + '.test[0].testA', 0)
        mc.setAttr(cube + '.test[1].testA', 1)

        attr = Node(cube).attrs['test']
        self.assertEqual(len(attr.children), 3)
        self.assertNotEqual(attr.children[1], 'test')
        self.assertEqual(attr.children[1], 'test[1]')
        self.assertEqual(attr.children[1].children[0], attr.children[1].children['testA'])
        self.assertEqual(attr.children[1].children[0], cube + '.test[1].testA')
        self.assertEqual(attr.children[1].children[0], 'test[1].testA')
        self.assertEqual(attr.children[1].children[0], 'testA')

        with self.assertRaises(KeyError):
            attr.children[3]
        with self.assertRaises(KeyError):
            attr.children[1].children['testB']

        mc.delete(cube)

    def testConnected(self):
        n1 = Node(mc.polyCube(name='testAttrConnection1')[0])
        n2 = Node(mc.polyCube(name='testAttrConnection2')[0])
        n1.attrs['tx'] >> n2.attrs['tx']
        n2.attrs['ty'] >> n1.attrs['ty']
        n1.attrs['tz'].keyframes[1].set()

        n1.attrs['tx'] = 1
        with self.assertRaises(exceptions.AttributeConnectedError):
            n1.attrs['ty'] = 1
        n1.attrs['tz'] = 1

        mc.delete(n1, n2)

    def testLogicalOnlyChildren(self):
        n = Node(mc.polyCube(name='logicalTest1')[0])

        na = n.attrs['tx']
        na.keyframes[5] = 5
        na.keyframes[0] = 0
        na.keyframes[7] = -5
        na.keyframes[10] = 10
        del na.keyframes[7]
        curve = na.connections[0].node
        ktv = curve.attrs['ktv']
        self.assertEqual(len(ktv.children), 3)
        self.assertEqual(ktv.children[1].children['keyValue'].value, 5)

        fa = n.shape.attrs['face']
        self.assertEqual(len(fa.children), 6)
        fa1 = fa.children[1]
        fa5 = fa.children[5]
        mc.delete(n + '.f[1]')
        self.assertTrue(fa1.exists)
        self.assertFalse(fa5.exists)

        mc.delete(n)

    def testChildElementNames(self):
        cam = Node(mc.camera(name='childElementTest')[0])
        mc.getAttr(cam + '.worldMatrix[1]')
        mc.getAttr(cam + '.worldMatrix[2]')
        self.assertEqual(len(cam.attrs['worldMatrix'].children), 2)
        with self.assertRaises(KeyError):
            cam.attrs['worldMatrix'].children[0]
        self.assertEqual(cam.attrs['worldMatrix'].children[1], cam + '.worldMatrix[1]')
        self.assertNotEqual(cam.attrs['worldMatrix'].children[1], cam + '.worldMatrix')
        self.assertNotEqual(cam.attrs['worldMatrix'].children[1], cam + '.worldMatrix[2]')
        mc.delete(cam)

    def testInvalidAttr(self):
        n = Node(mc.polyCube(name='invalidAttrTest')[0])
        with self.assertRaises(exceptions.InvalidAttributeTypeError):
            n.shape.attrs['face'].type
        with self.assertRaises(exceptions.InvalidAttributeTypeError):
            n.shape.attrs['face'].value
        mc.delete(n)

    def testRange(self):
        cube = Node(mc.polyCube(name='attrRangeTest1')[0])
        attr = cube.shape.attrs['currentUVSet']
        self.assertIsNone(attr.min)
        self.assertIsNone(attr.max)

        attr = cube.shape.attrs['maxTriangles']
        self.assertEqual(attr.min, 1.0)
        self.assertIsNone(attr.softMin)
        self.assertIsNone(attr.softMax)
        self.assertIsNone(attr.max)
        value = attr.value
        with self.assertRaises(exceptions.AttributeTooLowError):
            attr.value = 0
        self.assertEqual(attr.value, value)
        attr.value = 1
        self.assertNotEqual(attr.value, value)

        cam = Node(mc.camera(name='attrRangeTest2')[0])
        attr = cam.shape.attrs['verticalFilmAperture']
        self.assertEqual(round(attr.min, 5), 4e-05)
        self.assertEqual(attr.max, 1200.0)
        self.assertEqual(attr.softMax, 10.0)
        self.assertEqual(attr.softMin, 0.1)

        attr.value = 4e-05
        self.assertEqual(attr.value, 4e-05)
        with self.assertRaises(exceptions.AttributeTooLowError):
            attr.value = 3e-05
        self.assertEqual(attr.value, 4e-05)
        attr.value = 1200
        self.assertEqual(attr.value, 1200)
        with self.assertRaises(exceptions.AttributeTooHighError):
            attr.value = 1201
        self.assertEqual(attr.value, 1200)

        mc.delete(cube, cam)


class TestKeyframes(unittest.TestCase):
    def setUp(self):
        self.node = Node(mc.camera(name='keyframeTest')[0])
        for i in range(3):
            mc.setKeyframe(self.node + '.translateX', time=(i, i), value=-i)
        mc.setKeyframe(self.node + '.translateX', time=(3, 5), value=10)
        mc.setKeyframe(self.node + '.translateY', time=(0, 0), value=0)
        mc.setKeyframe(self.node.shape + '.focalLength', time=(2, 2), value=55)
        mc.setKeyframe(self.node.shape + '.focalLength', time=(7, 7), value=35)

    def tearDown(self):
        mc.delete(self.node)

    def testLength(self):
        self.assertEqual(len(self.node.keyframes), 8)
        self.assertEqual(len(self.node.attrs['tx'].keyframes), 5)
        self.assertEqual(len(self.node.shape.attrs['focalLength'].keyframes), 2)

        mc.cutKey(self.node, attribute='tx')
        self.assertEqual(len(self.node.attrs['tx'].keyframes), 0)
        self.assertFalse(self.node.attrs['tx'].keyframes)
        self.assertEqual(len(self.node.keyframes), 3)
        self.assertTrue(self.node.keyframes)
        mc.cutKey(self.node)
        self.assertFalse(self.node.keyframes)

    def testAttrs(self):
        self.assertEqual({a.attr for a in self.node.keyframes.attrs}, {'translateX', 'translateY', 'focalLength'})

    def testFrames(self):
        self.assertEqual(self.node.keyframes.keys(), [0.0, 0.0, 1.0, 2.0, 2.0, 3.0, 5.0, 7.0])
        self.assertEqual(self.node.attrs['tx'].keyframes.keys(), [0.0, 1.0, 2.0, 3.0, 5.0])

    # def testIter(self):
    #     seenAttrs = []
    #     seenFrames = []
    #     seenAttrFrames = []
    #     for kf in self.node.keyframes:
    #         seenAttrs.append(kf.attr)
    #         seenFrames.append(kf.frame)
    #         seenAttrFrames.append((kf.attr, kf.frame))
    #     uniqueAttrs = set(seenAttrs)
    #     uniqueFrames = set(seenFrames)
    #     uniqueAttrFrames = set(seenAttrFrames)
    #     self.assertNotEqual(len(seenAttrs), len(uniqueAttrs))
    #     self.assertNotEqual(len(seenFrames), len(uniqueFrames))
    #     self.assertEqual(len(seenAttrFrames), len(uniqueAttrFrames))

    #     seenAttrs = []
    #     seenFrames = []
    #     seenAttrFrames = []
    #     for kf in self.node.attrs['tx'].keyframes:
    #         seenAttrs.append(kf.attr)
    #         seenFrames.append(kf.frame)
    #         seenAttrFrames.append((kf.attr, kf.frame))
    #     uniqueAttrs = set(seenAttrs)
    #     uniqueFrames = set(seenFrames)
    #     uniqueAttrFrames = set(seenAttrFrames)
    #     self.assertNotEqual(len(seenAttrs), len(uniqueAttrs))
    #     self.assertEqual(uniqueAttrs, {self.node.attrs['tx']})
    #     self.assertEqual(len(seenFrames), len(uniqueFrames))
    #     self.assertEqual(len(uniqueFrames), 5)
    #     self.assertEqual(len(seenAttrFrames), len(uniqueAttrFrames))

    def testAttrGet(self):
        self.assertEqual(self.node.attrs['tx'].keyframes[0].value, 0.0)
        self.assertEqual(self.node.attrs['tx'].keyframes[1].value, -1.0)
        self.assertEqual(self.node.attrs['tx'].keyframes[2.0].value, -2.0)
        self.assertIsNone(self.node.attrs['tx'].keyframes[4].value)
        self.assertEqual(self.node.attrs['tx'].keyframes.values(), [0.0, -1.0, -2.0, 10.0, 10.0])

    def testNodeGet(self):
        self.assertEqual(list(self.node.keyframes[0])[0].value, 0.0)
        self.assertFalse(list(self.node.keyframes[10]))
        self.assertEqual(list(self.node.keyframes[1])[0].value, -1.0)

    def testAttrGetSlice(self):
        self.assertEqual(self.node.attrs['tx'].keyframes[0:3].value, [0.0, -1.0, -2.0, 10.0])
        self.assertEqual(self.node.attrs['tx'].keyframes[4:5].value, [10.0])

    def testNodeGetSlice(self):
        self.assertEqual(self.node.keyframes[1:6].keys(), [1.0, 2.0, 2.0, 3.0, 5.0])
        self.assertEqual(self.node.keyframes[1:6].values(), ['tx', 'tx', 'fl', 'tx', 'tx'])
        self.assertEqual(self.node.keyframes[1:6].items(), [(1.0, 'tx'), (2.0, 'tx'), (2.0, 'fl'), (3.0, 'tx'), (5.0, 'tx')])
        self.assertEqual(list(self.node.keyframes[1:6])[0].frame, 1.0)
        self.assertEqual(list(self.node.keyframes[1:6])[1].frame, 2.0)
        self.assertEqual(list(self.node.keyframes[1:6])[2].frame, 2.0)

    def testAttrGetSliceIncomplete(self):
        self.assertEqual(self.node.attrs['tx'].keyframes[:3].keys(), [0.0, 1.0, 2.0, 3.0])
        self.assertEqual(self.node.attrs['tx'].keyframes[3:].keys(), [3.0, 5.0])
        self.assertEqual(self.node.attrs['tx'].keyframes[3:].values(), [10.0, 10.0])
        self.assertEqual(self.node.attrs['tx'].keyframes[3:].items(), [(3.0, 10.0), (5.0, 10.0)])
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[5::2].keys()
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[:5:2].keys()
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[::2].keys()

    def testNodeGetSliceIncomplete(self):
        self.assertEqual(self.node.keyframes[:5].keys(), [0.0, 0.0, 1.0, 2.0, 2.0, 3.0, 5.0])
        self.assertEqual(self.node.keyframes[5:].keys(), [5.0, 7.0])
        self.assertEqual(self.node.keyframes[5:].values(), ['tx', 'fl'])
        self.assertEqual(self.node.keyframes[5:].items(), [(5.0, 'tx'), (7.0, 'fl')])
        with self.assertRaises(ValueError):
            self.node.keyframes[5::2].keys()
        with self.assertRaises(ValueError):
            self.node.keyframes[:5:2].keys()
        with self.assertRaises(ValueError):
            self.node.keyframes[::2].keys()

    def testSetNodeAll(self):
        self.assertIn(1, self.node.keyframes.keys())
        self.assertNotIn(50, self.node.keyframes.keys())
        mc.currentTime(50)
        self.node.keyframes.set()
        mc.currentTime(1)
        self.node.keyframes.set()
        self.assertIn(1, self.node.keyframes.keys())
        self.assertIn(50, self.node.keyframes.keys())

    def testSetNodeFrame(self):
        self.node.keyframes[10].set(-5)
        values = [kf.value for kf in self.node.keyframes[10]]
        keyable = [attr for attr in self.node.attrs.values() if attr.keyable]
        keyable.extend(attr for attr in self.node.shape.attrs.values() if attr.keyable)
        self.assertEqual(len(values), len(keyable))
        self.assertEqual(set(values), {-5})

    def testSetAttrFrame(self):
        self.node.attrs['tx'].keyframes[2] = -10
        self.node.attrs['tx'].keyframes[3].set(-20, outTangentType='step')
        self.assertEqual(self.node.attrs['tx'].keyframes[1].value, -1)
        self.assertEqual(self.node.attrs['tx'].keyframes[2].value, -10)
        self.assertEqual(self.node.attrs['tx'].keyframes[3].value, -20)
        self.assertIsNone(self.node.attrs['tx'].keyframes[4].value)

    def testSetNodeSlice(self):
        self.node.keyframes[10:15].set(-5)
        values = [kf.value for kf in self.node.keyframes[11:12]]
        keyable = [attr for attr in self.node.attrs.values() if attr.keyable]
        keyable.extend(attr for attr in self.node.shape.attrs.values() if attr.keyable)
        self.assertEqual(len(values), len(keyable) * 2)
        self.assertEqual(set(values), {-5})

    def testSetAttrSlice(self):
        self.node.attrs['tx'].keyframes[1:3] = -10
        self.node.attrs['tx'].keyframes[3:5].set(-20, outTangentType='step')
        self.assertEqual(self.node.attrs['tx'].keyframes[1].value, -10)
        self.assertEqual(self.node.attrs['tx'].keyframes[3:5].value, [-20, -20, -20])

    def testSetNodeIncompleteSlice(self):
        with self.assertRaises(ValueError):
            self.node.keyframes[:15].set(-5)
        with self.assertRaises(ValueError):
            self.node.keyframes[15:].set(-5)
        with self.assertRaises(ValueError):
            self.node.keyframes[:].set(-5)

    def testSetAttrSliceStepIncomplete(self):
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[:3] = -10
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[1:] = -10
        with self.assertRaises(ValueError):
            self.node.attrs['tx'].keyframes[:] = -10

    def testSetAttrSliceStep(self):
        self.node.attrs['tx'].keyframes[1:3] = -10
        self.node.attrs['tx'].keyframes[3:5:2].set(-20, outTangentType='step')
        self.assertEqual(self.node.attrs['tx'].keyframes[1].value, -10)
        self.assertEqual(self.node.attrs['tx'].keyframes[3:5].value, [-20, -20])

    def testAttrDelete(self):
        self.assertEqual(self.node.attrs['tx'].keyframes[1].value, -1)
        self.assertEqual(self.node.attrs['tx'].keyframes[5].value, 10)
        del self.node.attrs['tx'].keyframes[1]
        self.node.attrs['tx'].keyframes[5].delete()
        self.assertIsNone(self.node.attrs['tx'].keyframes[1].value)
        self.assertIsNone(self.node.attrs['tx'].keyframes[5].value)
        self.assertIsNotNone(self.node.attrs['tx'].keyframes[2].value)

    def testDeleteAttrKeyword(self):
        self.assertTrue(self.node.attrs['tx'].keyframes)
        del self.node.attrs['tx'].keyframes
        self.assertFalse(self.node.attrs['tx'].keyframes)

    def testDeleteAttrMethod(self):
        self.assertTrue(self.node.attrs['tx'].keyframes)
        self.node.attrs['tx'].keyframes.delete()
        self.assertFalse(self.node.attrs['tx'].keyframes)

    def testDeleteNodeKeyword(self):
        self.assertTrue(self.node.keyframes)
        self.assertTrue(self.node.attrs['tx'].keyframes)
        self.assertTrue(self.node.attrs['tx'].keyframes)
        del self.node.keyframes
        self.assertFalse(self.node.keyframes)
        self.assertFalse(self.node.attrs['tx'].keyframes)
        self.assertFalse(self.node.shape.attrs['focalLength'].keyframes)

    def testDeleteNodeMethod(self):
        self.assertTrue(self.node.keyframes)
        self.assertTrue(self.node.attrs['tx'].keyframes)
        self.assertTrue(self.node.attrs['tx'].keyframes)
        self.node.keyframes.delete()
        self.assertFalse(self.node.keyframes)
        self.assertFalse(self.node.attrs['tx'].keyframes)
        self.assertFalse(self.node.shape.attrs['focalLength'].keyframes)

    def testDeleteSlice(self):
        frames = self.node.attrs['tx'].keyframes.keys()
        self.assertNotEqual(self.node.attrs['tx'].keyframes[1:10:2].values(), [])
        del self.node.attrs['tx'].keyframes[1:10:2]
        self.assertEqual(set(self.node.attrs['tx'].keyframes.keys()), set(frames) - set(range(1, 10, 2)))

    def testOffsetNode(self):
        frames = list(self.node.keyframes.keys())
        self.node.keyframes.offset(1)
        self.assertEqual(self.node.keyframes.keys(), [i + 1 for i in frames])

    def testOffsetNodeInt(self):
        self.node.keyframes[2].offset(2)
        self.assertIn(4, self.node.keyframes.keys())

    def testOffsetNodeSlice(self):
        self.assertEqual(len(self.node.keyframes[0:2].keys()), 5)
        self.node.keyframes[0:2].offset(3)
        self.assertEqual(len(self.node.keyframes[0:2].keys()), 0)
        self.node.keyframes.offset(-3)
        self.assertEqual(len(self.node.keyframes[0:2].keys()), 4)
        self.assertEqual([round(k) for k in self.node.keyframes[-1:0].keys()], [0, 0, 0, 0, 0])

    def testOffsetAttr(self):
        frames = list(self.node.attrs['tx'].keyframes.keys())
        self.node.attrs['tx'].keyframes.offset(1)
        self.assertEqual(self.node.attrs['tx'].keyframes.keys(), [i + 1 for i in frames])
        self.node.attrs['tx'].keyframes.offset(1)
        self.assertEqual(self.node.attrs['tx'].keyframes.keys(), [i + 2 for i in frames])

    def testOffsetAttrInt(self):
        self.node.attrs['tx'].keyframes[3].offset(1)
        self.assertIn(4, self.node.attrs['tx'].keyframes.keys())
        self.assertNotIn(3, self.node.attrs['tx'].keyframes.keys())

    def testOffsetAttrSlice(self):
        self.assertEqual(self.node.attrs['tx'].keyframes.keys(), [0, 1, 2, 3, 5])
        self.assertEqual(self.node.attrs['tx'].keyframes[2:6].keys(), [2, 3, 5])
        self.node.attrs['tx'].keyframes[2:6].offset(3)
        self.assertEqual(self.node.attrs['tx'].keyframes[2:6].keys(), [5, 6])
        self.node.attrs['tx'].keyframes[2:6].offset(1)
        self.assertEqual(self.node.attrs['tx'].keyframes[2:6].keys(), [6])
        self.node.attrs['tx'].keyframes.offset(-4)
        self.assertEqual(self.node.attrs['tx'].keyframes.keys(), [-4, -3, 2, 3, 4])

    def testAdd(self):
        r = lambda lst: [round(i, 4) for i in lst]
        frames = r(self.node.keyframes.keys())
        for keyframe in self.node.keyframes:
            keyframe.frame += 0.5
        self.assertEqual(r(self.node.keyframes.keys()), [i + 0.5 for i in frames])

        frames = r(self.node.attrs['tx'].keyframes.keys())
        for keyframe in self.node.attrs['tx'].keyframes:
            keyframe.frame += 0.5
        self.assertEqual(r(self.node.attrs['tx'].keyframes.keys()), [i + 0.5 for i in frames])

    def testLockedAttr(self):
        attr = self.node.attrs['tx']

        self.assertIsNone(attr.keyframes[100].value)
        attr.keyframes[100].value = 5
        self.assertEqual(attr.keyframes[100].value, 5)
        attr.keyframes.lock()
        with self.assertRaises(exceptions.LockedKeyframeError):
            attr.keyframes[100].value = 1
        with self.assertRaises(exceptions.LockedKeyframeError):
            del attr.keyframes[100]
        with self.assertRaises(exceptions.LockedKeyframeError):
            attr.keyframes[100].offset(1)
        self.assertEqual(attr.keyframes[100].value, 5)
        attr.keyframes.unlock()
        attr.keyframes[100].value = 1
        del attr.keyframes[100]
        self.assertIsNone(attr.keyframes[100].value)

    def testLockedAttrOnNode(self):
        attr = self.node.attrs['tx']

        attr.keyframes[100].value = 1
        attr.keyframes.lock()
        self.node.keyframes[100] = 5
        self.assertEqual(attr.keyframes[100].value, 1)
        with self.assertRaises(exceptions.LockedKeyframeError):
            attr.keyframes[100].value = 5
        del self.node.keyframes[100]
        self.assertEqual(attr.keyframes[100].value, 1)
        attr.keyframes.unlock()
        del self.node.keyframes[100]

    def testLockNonKeyframedAttr(self):
        with self.assertRaises(exceptions.KeyframeLockError):
            self.node.attrs['sz'].keyframes.lock()


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
        self.assertTrue(self.node.uvSet.exists)
        self.assertFalse(UVSet(self.node, 'map3').exists)

    def testLength(self):
        self.assertTrue(self.node.uvSets)
        self.assertEqual(len(self.node.uvSets), 2)

    def testRename(self):
        self.node.uvSet.name = 'renamed'
        self.assertEqual(self.node.uvSet, 'renamed')
        self.assertEqual(self.node.uvSets, ['renamed', 'map2'])

    def testRenameInUse(self):
        with self.assertRaises(exceptions.UVSetExistsError):
            self.node.uvSet.name = 'map2'

    def testModifierRename(self):
        with MayaNode() as context:
            dgMod = context.dgModifier = om2.MDGModifier()
            self.node.uvSet.name = 'map3'
        self.assertEqual(self.node.uvSet, 'map3')
        dgMod.undoIt()
        self.assertEqual(self.node.uvSet, 'map1')

    def testModifierRenameInUse(self):
        with MayaNode() as context:
            context.dgModifier = om2.MDGModifier()
            with self.assertRaises(exceptions.UVSetExistsError):
                self.node.uvSet.name = 'map2'
        self.assertEqual(self.node.uvSet, 'map1')

    def testSet(self):
        self.node.uvSet = 'map2'
        self.assertEqual(self.node.uvSet, 'map2')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testSetInvalid(self):
        with self.assertRaises(exceptions.UVSetNotFoundError):
            self.node.uvSet = 'map3'
        self.assertEqual(self.node.uvSet, 'map1')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testSetCurrent(self):
        self.assertFalse(self.node.uvSets['map2'].current)
        self.node.uvSets['map2'].current = True
        self.assertEqual(self.node.uvSet, 'map2')
        with self.assertRaises(ValueError):
            self.node.uvSets['map2'].current = False
        self.assertEqual(self.node.uvSet, 'map2')
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

    def testModifierSet(self):
        with MayaNode() as context:
            dgMod = context.dgModifier = om2.MDGModifier()
            self.node.uvSet = 'map2'
        self.assertEqual(self.node.uvSet, 'map2')
        dgMod.undoIt()
        self.assertEqual(self.node.uvSet, 'map1')

    def testDelete(self):
        with self.assertRaises(exceptions.UVSetDeleteDefaultError):
            self.node.uvSet.delete()
        self.node.uvSet = 'map2'
        self.node.uvSet.delete()
        self.assertEqual(self.node.uvSet, 'map1')
        self.assertEqual(self.node.uvSets, ['map1'])

    def testModifierDelete(self):
        with MayaNode() as context:
            dgMod = context.dgModifier = om2.MDGModifier()
            del self.node.uvSets['map2']
        self.assertEqual(self.node.uvSets, ['map1'])
        dgMod.undoIt()
        self.assertEqual(self.node.uvSets, ['map1', 'map2'])

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
        self.node = mc.polyCube(n=self.ns2 + ':namespaceTest')[0]

    def tearDown(self):
        if mc.objExists(self.node):
            mc.delete(self.node)
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

    def testRename(self):
        ns1 = Namespace(self.ns1)
        ns2 = Namespace(self.ns2)

        ns1.name = 'namespaceTestRenamed'
        self.assertFalse(ns2.exists)
        self.assertEqual(ns2, 'namespaceTest1:namespaceTest2')
        self.assertEqual(ns1.children, ['namespaceTestRenamed:namespaceTest2'])
        ns1.name = 'namespaceTest1'
        self.assertTrue(ns2.exists)

        self.assertFalse(Namespace('namespaceTestParent').exists)
        ns1.name = 'namespaceTestParent:namespaceTestChild'
        self.assertEqual(ns1, 'namespaceTestParent:namespaceTestChild')
        self.assertIn(ns1, Namespace('namespaceTestParent').children)
        self.assertFalse(ns2.exists)
        ns1.name = 'namespaceTest1'
        self.assertTrue(ns2.exists)

        self.assertTrue(Namespace('namespaceTestParent').exists)
        ns1.name = 'namespaceTestParent:namespaceTestChild'
        ns1.name = 'namespaceTest1'
        mc.namespace(removeNamespace='namespaceTestParent')

    def testRenameSelf(self):
        ns1 = Namespace(self.ns1)
        ns1.name = ns1

    def testRenameInvalid(self):
        with self.assertRaises(exceptions.NamespaceNotUniqueError):
            Namespace(self.ns3).name = self.ns1
        with self.assertRaises(exceptions.NamespaceInvalidNameError):
            Namespace(self.ns3).name = ':'
        with self.assertRaises(exceptions.NamespaceParentError):
            Namespace(self.ns1).name = self.ns3 + ':' + 'ns4'
        with self.assertRaises(exceptions.NamespaceParentError):
            Namespace(self.ns1).name = self.ns3.strip(':') + ':' + 'ns4'

    def testReparent(self):
        ns3 = Namespace(self.ns3)

        ns3.parent = self.ns1
        self.assertTrue(Namespace(self.ns1).exists)
        self.assertFalse(Namespace(self.ns3).exists)
        self.assertEqual(len(Namespace(self.ns1).children), 2)

        ns3.parent = self.ns2
        self.assertEqual(len(Namespace(self.ns1).children), 1)
        self.assertTrue(Namespace(self.ns3).exists)

        with self.assertRaises(exceptions.NamespaceParentError):
            Namespace(self.ns1).parent = self.ns2

    def testDeleteSimple(self):
        mc.delete(self.node)
        self.assertTrue(Namespace(self.ns3).delete())
        self.assertTrue(Namespace(self.ns2).delete())
        self.assertTrue(Namespace(self.ns1).delete())

    def testDeleteWithNamespace(self):
        mc.delete(self.node)
        with self.assertRaises(exceptions.NamespaceNotEmptyError):
            Namespace(self.ns2).delete()
        self.assertTrue(Namespace(self.ns3).delete())
        self.assertTrue(Namespace(self.ns2).delete())

    def testDeleteParamWithNamespace(self):
        with self.assertRaises(exceptions.NamespaceNotEmptyError):
            self.assertTrue(Namespace(self.ns2).delete(recursive=True))
        mc.delete(self.node)
        self.assertTrue(Namespace(self.ns2).delete(recursive=True))

    def testDeleteWithNode(self):
        self.assertTrue(Namespace(self.ns3).delete())
        with self.assertRaises(exceptions.NamespaceNotEmptyError):
            Namespace(self.ns2).delete()
        mc.delete(self.node)
        self.assertTrue(Namespace(self.ns2).delete())

    def testDeleteParamWithNode(self):
        with self.assertRaises(exceptions.NamespaceNotEmptyError):
            self.assertTrue(Namespace(self.ns2).delete(nodes=True))
        self.assertTrue(Namespace(self.ns3).delete())
        self.assertTrue(Namespace(self.ns2).delete(nodes=True))

    def testDeleteRecursive(self):
        self.assertTrue(Namespace(self.ns1).delete(nodes=True, recursive=True))
        self.assertFalse(mc.objExists(self.node))

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

    def testContains(self):
        cube = mc.polyCube(name='namespaceContainsTest')[0]
        node = Node(cube)
        namespace = node.namespace = Namespace(self.ns2)

        self.assertIn(cube, namespace.nodes)
        self.assertIn('{}:{}'.format(self.ns2, cube), namespace.nodes)
        self.assertIn('{}:{}'.format(self.ns2[1:], cube), namespace.nodes)
        self.assertIn('|{}:{}'.format(self.ns2, cube), namespace.nodes)

        mc.delete(node)
        self.assertNotIn(cube, namespace.nodes)

    def testStrip(self):
        ns1 = Namespace(self.ns1)
        self.assertEqual(ns1, ':namespaceTest1')
        self.assertEqual(ns1, 'namespaceTest1')

        self.assertEqual(str(ns1), ':namespaceTest1')
        self.assertNotEqual(str(ns1), 'namespaceTest1')

        self.assertEqual(str(ns1).strip(), ':namespaceTest1')
        self.assertNotEqual(str(ns1).strip(), 'namespaceTest1')

        self.assertNotEqual(ns1.strip(), ':namespaceTest1')
        self.assertEqual(ns1.strip(), 'namespaceTest1')
        self.assertEqual(ns1.lstrip(), 'namespaceTest1')
        self.assertEqual(ns1.rstrip(), ':namespaceTest1')

        self.assertFalse(Namespace(':').strip())
        self.assertFalse(Namespace(':').lstrip())
        self.assertFalse(Namespace(':').rstrip())


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


class TestReference(unittest.TestCase):
    _Header = '//Maya ASCII\nrequires maya "2018";'

    _CreateCube = ('createNode transform -n "pCube1";'
                   'createNode mesh -n "pCubeShape1" -p "pCube1";'
                   'createNode polyCube -n "polyCube1";'
                   'connectAttr "polyCube1.out" "pCubeShape1.i";'
                   'connectAttr "pCubeShape1.iog" ":initialShadingGroup.dsm" -na;')

    _CreateRef = ('file -rdi 1 -ns "ref{n}" -rfn "ref{n}RN" -typ "mayaAscii" "{path}";'
                  'file -r -ns "ref{n}" -dr 1 -rfn "ref{n}RN" -typ "mayaAscii" "{path}";'
                  'createNode reference -n "ref{n}RN";'
                  'lockNode -l 1;')

    def setUp(self):
        self.refPaths = []
        self.refDir = tempfile.mkdtemp('-mayanode-tests')
        for i in range(3):
            refPath = os.path.join(self.refDir, 'ref{}.ma'.format('ABC'[i])).replace('\\', '/')

            sections = [self._Header, self._CreateCube]
            if i:
                sections.append(self._CreateRef.format(n='ABC'[i - 1], path=self.refPaths[-1]))
            with open(refPath, 'w') as f:
                f.write('\n'.join(sections))
            self.refPaths.append(refPath)
        self.refFile = File(self.refPaths[-1])

    def tearDown(self):
        for refPath in self.refPaths:
            os.remove(refPath)
        os.rmdir(self.refDir)

    def testNamespace(self):
        rn1 = self.refFile.reference()
        self.assertEqual(rn1.namespace, ':refC')
        rn2 = self.refFile.reference(namespace='refD')
        self.assertEqual(rn2.namespace, ':refD')
        rn3 = self.refFile.reference(namespace='refD')
        self.assertEqual(rn3.namespace, ':refD1')
        rn4 = self.refFile.reference(namespace=None)
        self.assertEqual(rn4.namespace, ':')

        mc.file(rn1.refPath, unloadReference=True)
        self.assertEqual(rn1.namespace, ':refC')
        rn1.namespace.delete(recursive=True)
        self.assertEqual(rn1.namespace, ':refC')

        rn1.delete()
        rn2.delete()
        rn3.delete()
        rn4.delete(forceRemoveNamespaces=True)

    def testFromNamespace(self):
        rn1 = self.refFile.reference()
        self.assertEqual(rn1.namespace.reference, rn1)
        self.assertEqual(Reference.fromNamespace(rn1.namespace), rn1)
        rn1.delete(forceRemoveNamespaces=True)

    def testNamespaceEdit(self):
        rn1 = self.refFile.reference()
        rn2 = self.refFile.reference(namespace='refD')
        rn3 = self.refFile.reference(namespace=None)

        rn1.namespace = 'refD'
        self.assertEqual(rn2.namespace, 'refD')
        self.assertNotEqual(rn1.namespace, 'refD')
        rn1.namespace = 'refE'
        self.assertEqual(rn1.namespace, 'refE')

        rn1.unload()
        with self.assertRaises(exceptions.UnloadedReferenceNamespaceError):
            rn1.namespace = 'refF'

        with self.assertRaises(exceptions.ReferenceWithoutNamespaceError):
            rn3.namespace = 'refG'
        self.assertEqual(rn3.namespace, ':')

        rn1.delete()
        rn2.delete()
        rn3.delete(forceRemoveNamespaces=True)

    def testLs(self):
        loadedRefNode = self.refFile.reference(defer=False)
        unloadedRefNode = self.refFile.reference(defer=True)

        self.assertEqual(len(Reference.ls()), 4)
        self.assertEqual([loadedRefNode], Reference.ls(str(loadedRefNode)))
        self.assertEqual([unloadedRefNode], Reference.ls(str(unloadedRefNode)))
        self.assertEqual(len(Reference.ls('ref*')), 2)
        self.assertEqual(len(Reference.ls('*:ref*')), 1)
        self.assertEqual(len(Reference.ls('*:*:*ref*')), 1)

        self.assertEqual(len(Reference.ls(loaded=True)), 3)
        self.assertEqual(len(Reference.ls('ref*', loaded=True)), 1)
        self.assertEqual(len(Reference.ls(loaded=False)), 1)

        loadedRefNode.delete()
        unloadedRefNode.delete()

    def testLoad(self):
        loadedRefNode = self.refFile.reference(defer=False)
        unloadedRefNode = self.refFile.reference(defer=True)

        self.assertTrue(loadedRefNode.loaded)
        self.assertFalse(unloadedRefNode.loaded)
        loadedRefNode.unload()
        unloadedRefNode.load()
        self.assertTrue(unloadedRefNode.loaded)
        self.assertFalse(loadedRefNode.loaded)
        loadedRefNode.loaded = True
        unloadedRefNode.loaded = False
        self.assertTrue(loadedRefNode.loaded)
        self.assertFalse(unloadedRefNode.loaded)

        loadedRefNode.delete()
        unloadedRefNode.delete()

    def testDelete(self):
        existingNodes = Node.ls()
        existingNs = Namespace.ls()
        rn = self.refFile.reference()
        rn.delete()
        self.assertEqual(Node.ls(), existingNodes)
        self.assertEqual(Namespace.ls(), existingNs)
        rn = self.refFile.reference(namespace=None)
        rn.delete(forceRemoveNamespaces=True)
        self.assertEqual(Node.ls(), existingNodes)
        self.assertEqual(Namespace.ls(), existingNs)
        rn = self.refFile.reference(namespace=None)
        rn.delete()
        self.assertEqual(Node.ls(), existingNodes)
        self.assertNotEqual(Namespace.ls(), existingNs)
        for ns in sorted(set(Namespace.ls()) - set(existingNs),
                         key=lambda ns: str(ns).count(':'), reverse=True):
            ns.delete()
        self.assertEqual(Namespace.ls(), existingNs)

    def testNodesGet(self):
        refNode = self.refFile.reference()
        self.assertEqual(refNode.nodes[0], 'pCube1')
        self.assertIn('pCube1', refNode.nodes)
        self.assertIn(refNode.namespace + ':pCube1', refNode.nodes)
        self.assertEqual(refNode, refNode.nodes.reference)
        self.assertNotIn(refNode.children[0].namespace + ':pCube1', refNode.nodes)

        node = refNode.nodes['pCube1']
        self.assertIn(node, refNode.nodes)
        self.assertEqual(node.namespace, refNode.namespace)
        self.assertNotEqual(node.name, 'pCube1')

        refNode.unload()
        self.assertFalse(refNode.nodes)
        self.assertNotIn(refNode.namespace + ':pCube1', refNode.nodes)
        self.assertNotIn(node, refNode.nodes)
        refNode.delete()

    def testNodesLength(self):
        refNode = self.refFile.reference()
        self.assertEqual(len(refNode.nodes), 4)
        refNode.delete()

    def testNodesSlice(self):
        refNode = self.refFile.reference()
        self.assertEqual(refNode.nodes, refNode.nodes[:2] + refNode.nodes[2:])
        self.assertNotEqual(refNode.nodes, refNode.nodes[2:] + refNode.nodes[:2])
        refNode.delete()

    def testLock(self):
        loadedRefNode = self.refFile.reference(defer=False)
        unloadedRefNode = self.refFile.reference(defer=True)

        self.assertFalse(loadedRefNode.locked)
        self.assertFalse(unloadedRefNode.locked)
        loadedRefNode.lock()
        unloadedRefNode.locked = True
        self.assertTrue(loadedRefNode.locked)
        self.assertTrue(unloadedRefNode.locked)
        self.assertTrue(loadedRefNode.loaded)
        self.assertFalse(unloadedRefNode.loaded)
        loadedRefNode.unlock()
        unloadedRefNode.locked = False
        self.assertFalse(loadedRefNode.locked)
        self.assertFalse(unloadedRefNode.locked)
        self.assertTrue(loadedRefNode.loaded)
        self.assertFalse(unloadedRefNode.loaded)

        loadedRefNode.delete()
        unloadedRefNode.delete()

    def testDepth(self):
        refNode = self.refFile.reference()
        nested = Reference.ls(refNode.namespace + ':*:*')[0]
        self.assertTrue(refNode.topLevel)
        self.assertFalse(nested.topLevel)
        self.assertEqual(refNode.depth, 0)
        self.assertEqual(nested.depth, 2)

        refNode.delete()

    def testRelationships(self):
        refNode = self.refFile.reference()
        nested = Reference.ls(refNode.namespace + ':*:*')[0]

        self.assertIn(nested, refNode.descendents)
        self.assertNotIn(nested, refNode.children)
        self.assertIn(nested.parent, refNode.children)
        self.assertIn(refNode, nested.ancestors)
        self.assertNotEqual(refNode, nested.parent)
        self.assertEqual(refNode.children[0], nested.parent)

        refNode.delete()

    def testImport(self):
        refNode = self.refFile.reference()
        nodes = list(refNode.nodes)
        for node in nodes:
            self.assertTrue(node.exists)
            self.assertIsNotNone(node.reference)

        refNode.import_()

        self.assertFalse(refNode.exists)
        for node in nodes:
            self.assertTrue(node.exists)
            self.assertIsNone(node.reference)
            if node.type == 'reference':
                self.assertTrue(Reference(node).topLevel)

        namespaces = set()
        for node in nodes:
            if not node.exists:
                continue
            namespaces.add(node.namespace)
            if node.type == 'reference':
                Reference(node).delete(forceRemoveNamespaces=True)
            elif node.type == 'transform':
                node.delete()
        for namespace in namespaces:
             Namespace(namespace).delete()

    def testImportChild(self):
        refNode = self.refFile.reference()

        childRefNode = refNode.children[0]
        with self.assertRaises(exceptions.NotATopLevelReferenceImportError):
            childRefNode.import_()

        refNode.delete()

    def testImportUnloaded(self):
        refNode = self.refFile.reference(defer=True)

        with self.assertRaises(exceptions.UnloadedReferenceImportError):
            refNode.import_()

        refNode.delete()

    def testRenameNode(self):
        refNode = self.refFile.reference()
        with self.assertRaises(exceptions.RenameReferencedNodeError):
            refNode.nodes['pCube1'].name = 'refRenameTest'
        refNode.nodes['pCube1'].unlock()
        with self.assertRaises(exceptions.RenameReferencedNodeError):
            refNode.nodes['pCube1'].name = 'refRenameTest'
        refNode.delete()

    def testRenameRefNode(self):
        loadedRefNode = self.refFile.reference(defer=False)
        unloadedRefNode = self.refFile.reference(defer=True)

        loadedRefNode.name = 'renameRefTestLoaded1'
        unloadedRefNode.name = 'renameRefTestUnloaded1'

        with self.assertRaises(exceptions.RenameLockedNodeError):
            loadedRefNode.refNode.name = 'renameRefTestLoaded2'
        with self.assertRaises(exceptions.RenameLockedNodeError):
            unloadedRefNode.refNode.name = 'renameRefTestUnloaded2'

        loadedRefNode.lock()
        unloadedRefNode.lock()

        loadedRefNode.name = 'renameRefTestLoaded3'
        unloadedRefNode.name = 'renameRefTestUnloaded3'

        loadedRefNode.refNode.unlock()
        unloadedRefNode.refNode.unlock()

        loadedRefNode.name = 'renameRefTestLoaded4'
        unloadedRefNode.name = 'renameRefTestUnloaded4'

        loadedRefNode.delete()
        unloadedRefNode.delete()


class TestFile(unittest.TestCase):
    def testEquality(self):
        self.assertEqual(File('C:/a/b'), 'C:/a/b')
        self.assertEqual(File('C:/a/b'), 'c:/A/B')
        self.assertEqual(File('C:/a/b'), 'C:/a/b/')
        self.assertEqual(File('C:/a/b/'), 'C:/a/b/')
        self.assertEqual(File('C:/a/b/'), 'C:/a/b')
        self.assertEqual(File('C:/a/b/'), File('C:/a/b'))
        self.assertEqual(File('C:/a/b/'), r'C:\a\b')
        self.assertNotEqual(File('C:/a/b/'), 'C:/a')
        self.assertNotEqual(File('C:/a/b/'), 'C:/a/b/c')
        self.assertNotEqual(File('C:/a/b/'), [])
        self.assertNotEqual(File('C:/a/b/'), 0)

    def testOS(self):
        self.assertEqual(os.path.join(File('C:/a'), 'b'), r'C:\a\b')

    def testParent(self):
        self.assertEqual(File('C:/a/b').parent, 'C:/a')

    def testName(self):
        self.assertEqual(File('c:/a').name, 'a')
        self.assertEqual(File('c:/a').filename, 'a')
        self.assertEqual(File('c:/a').ext, '')
        self.assertEqual(File('c:/a.txt').name, 'a')
        self.assertEqual(File('c:/a.txt').filename, 'a.txt')
        self.assertEqual(File('c:/a.txt').ext, 'txt')
        self.assertEqual(File('c:/a.b.txt').name, 'a.b')
        self.assertEqual(File('c:/a.b.txt').filename, 'a.b.txt')
        self.assertEqual(File('c:/a.b.txt').ext, 'txt')

    def testResolved(self):
        os.environ['MN_TEST'] = 'C:/folder'
        self.assertEqual(File('$MN_TEST/subfolder'), '$MN_TEST/subfolder')
        self.assertNotEqual(File('$MN_TEST/subfolder'), 'C:/folder/subfolder')
        self.assertNotEqual(File('$MN_TEST/subfolder').resolved, '$MN_TEST/subfolder')
        self.assertEqual(File('$MN_TEST/subfolder').resolved, 'C:/folder/subfolder')
        self.assertEqual(File('$MN_TEST/subfolder').resolved.resolved, 'C:/folder/subfolder')
        del os.environ['MN_TEST']


class TestVersion(unittest.TestCase):
    def setUp(self):
        self.version = mc.about(version=True)
        self.major = mc.about(majorVersion=True)
        self.minor = mc.about(minorVersion=True)
        self.patch = mc.about(patchVersion=True)

    def testComparison(self):
        self.assertEqual(Maya.version, mc.about(version=True))
        self.assertEqual(Maya.version, self.major)
        self.assertEqual(Maya.version, int(self.major))
        self.assertEqual(int(Maya.version), int(self.major))
        self.assertEqual(Maya.version, '{}.{}'.format(self.major, self.minor))
        self.assertEqual(Maya.version, float('{}.{}'.format(self.major, self.minor)))
        self.assertEqual(float(Maya.version), float('{}.{}'.format(self.major, self.minor)))
        self.assertEqual(Maya.version, '{}.{}.{}'.format(self.major, self.minor, self.patch))
        self.assertTrue(Maya.version < (int(self.major) + 1))
        self.assertTrue(Maya.version > 0.0)
        self.assertFalse(Maya.version < '0')
        self.assertFalse(Maya.version > '')
        self.assertFalse(Maya.version > 'string')

    def testTokenise(self):
        self.assertEqual(tokeniseVersion('1'), [1])
        self.assertEqual(tokeniseVersion('1.2'), [1, 2])
        self.assertEqual(tokeniseVersion('1v2'), [1, 2])
        self.assertEqual(tokeniseVersion('1.2.3'), [1, 2, 3])
        self.assertEqual(tokeniseVersion('1.2.3v4'), [1, 2, 3, 4])
        self.assertEqual(tokeniseVersion('1.2.03v04'), [1, 2, 3, 4])
        self.assertEqual(tokeniseVersion('1.2.30v40'), [1, 2, 30, 40])
        self.assertEqual(tokeniseVersion('1.2.3v4a'), [1, 2, 3, 4, 'a'])
        self.assertEqual(tokeniseVersion('a'), ['a'])
        self.assertEqual(tokeniseVersion('a1'), ['a', 1])
        self.assertEqual(tokeniseVersion('a1a'), ['a', 1, 'a'])
        self.assertEqual(tokeniseVersion('a.b'), ['a', 'b'])
        self.assertEqual(tokeniseVersion('v1'), [1])
        self.assertEqual(tokeniseVersion('v1', False), ['v', 1])
        self.assertEqual(tokeniseVersion('12.ab.c34d.5ef6'), [12, 'ab', 'c34d', 5, 6])
        self.assertEqual(tokeniseVersion(1), [1])
        self.assertEqual(tokeniseVersion(1.2), [1, 2])

    def testStandardise(self):
        self.assertEqual(standardiseVersions('1.2.3', '1.2.3'), ([1, 2, 3], [1, 2, 3]))
        self.assertEqual(standardiseVersions(1, 2), (1, 2))
        self.assertEqual(standardiseVersions(1, 1.2), (1, 1))
        self.assertEqual(standardiseVersions(1.2, 1), (1, 1))
        self.assertEqual(standardiseVersions(1.2, '1'), (1, 1))
        self.assertEqual(standardiseVersions(1.2, '1.2.3'), ([1, 2], [1, 2]))
        self.assertEqual(standardiseVersions(1, '1.2.3'), (1, 1))
        self.assertEqual(standardiseVersions(1.2, 'v2'), (1, 2))
        self.assertEqual(standardiseVersions(1.2, 'v'), (1, 'v'))
        self.assertEqual(standardiseVersions(1.2, '1.2v3'), ([1, 2], [1, 2]))
        self.assertEqual(standardiseVersions(1.2, '1v2'), ([1, 2], [1, 2]))
        self.assertEqual(standardiseVersions('1v2', 1.2), ([1, 2], [1, 2]))
        self.assertEqual(standardiseVersions('1.2.3', '1.2.3v4'), ([1, 2, 3], [1, 2, 3]))
        self.assertEqual(standardiseVersions('1.2.3', '1.2.34'), ([1, 2, 3], [1, 2, 34]))
        self.assertEqual(standardiseVersions('1.2.3', 'v1.2.3'), ([1, 2, 3], [1, 2, 3]))
        self.assertEqual(standardiseVersions('v1.2.3', 'v1.2'), ([1, 2], [1, 2]))
        self.assertEqual(standardiseVersions('v1.2.3', 1), (1, 1))
        self.assertEqual(standardiseVersions(1, 'v1.2.3'), (1, 1))
        self.assertEqual(standardiseVersions('1.2v3a', '1.2v3b'), ([1, 2, 3, 'a'], [1, 2, 3, 'b']))
        self.assertEqual(standardiseVersions('1.2v3a', '1.2v3'), ([1, 2, 3], [1, 2, 3]))
        self.assertEqual(standardiseVersions('a.1', 'a.2'), (['a', 1], ['a', 2]))
        self.assertEqual(standardiseVersions('a.b', 'a.2'), (['a', 'b'], ['a', 2]))


class TestScene(unittest.TestCase):
    def testRoot(self):
        self.assertEqual(Scene.root, 'world')
        self.assertIn('persp', Scene.root.children)

    def testNodes(self):
        self.assertIn('persp', Scene.nodes)
        self.assertIn(Node('persp'), Scene.nodes)
        self.assertNotIn('test', Scene.nodes)
        self.assertEqual(set(Scene.nodes.values()), set(Node.ls()))
        self.assertEqual(Node('persp'), Scene.nodes['persp'])


class TestMesh(unittest.TestCase):
    def setUp(self):
        self.node = Node(mc.polyCube(name='meshTest')[0]).shape

    def tearDown(self):
        mc.delete(self.node.parent)

    def testFaces(self):
        self.assertEqual(self.node.faces, self.node + '.f[0:5]')
        self.assertEqual(str(self.node.faces), self.node + '.f[0:5]')
        self.assertEqual(self.node.faces.name, self.node + '.f[0:5]')
        self.assertEqual(self.node.faces, ['{}.f[{}]'.format(self.node, i) for i in range(6)])
        self.assertEqual(repr(self.node.faces), repr([self.node.faces[i] for i in range(6)]))

        self.assertEqual(len(self.node.faces), 6)
        self.assertEqual(self.node.faces[1], '{}.f[1]'.format(self.node))
        self.assertIn('map1', self.node.faces[1].uvSets)


if __name__ == '__main__':
    unittest.main()

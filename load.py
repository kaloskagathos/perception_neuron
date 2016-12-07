# Edward Lee edl56@cornell.edu
# Classes:
# Node, Tree
# 2016-08-11

from __future__ import division
import pandas as pd
import numpy as np

def calc_file_body_parts():
    """
    According to ref file sent by Noitom.
    2016-11-13
    """
    return ['Hips',
            'RightUpLeg',
            'RightLeg',
            'RightFoot',
            'LeftUpLeg',
            'LeftLeg',
            'LeftFoot',
            'RightShoulder',
            'RightArm',
            'RightForeArm',
            'RightHand',
            'LeftShoulder',
            'LeftArm',
            'LeftForeArm',
            'LeftHand',
            'Head',
            'Neck',
            'Spine3',
            'Spine2',
            'Spine1',
            'Spine',
            'left foot contact',
            'right foot contact',
            'RightHandThumb1',
            'RightHandThumb2',
            'RightHandThumb3',
            'RightInHandIndex',
            'RightHandIndex1',
            'RightHandIndex2',
            'RightHandIndex3',
            'RightInHandMiddle',
            'RightHandMiddle1',
            'RightHandMiddle2',
            'RightHandMiddle3',
            'RightInHandRing',
            'RightHandRing1',
            'RightHandRing2',
            'RightHandRing3',
            'RightInHandPinky',
            'RightHandPinky1',
            'RightHandPinky2',
            'RightHandPinky3',
            'LeftHandThumb1',
            'LeftHandThumb2',
            'LeftHandThumb3',
            'LeftInHandIndex',
            'LeftHandIndex1',
            'LeftHandIndex2',
            'LeftHandIndex3',
            'LeftInHandMiddle',
            'LeftHandMiddle1',
            'LeftHandMiddle2',
            'LeftHandMiddle3',
            'LeftInHandRing',
            'LeftHandRing1',
            'LeftHandRing2',
            'LeftHandRing3',
            'LeftInHandPinky',
            'LeftHandPinky1',
            'LeftHandPinky2',
            'LeftHandPinky3']

def load_calc(fname,cols='V'):
    """
    Load calculation file output by Axis Neuron. Rotate given vectors such that z-axis faces along given Zd
    direction in calc file.
    Be  careful because z-axis points into the ground by default.
    2016-12-05

    Params:
    -------
    fname (str)
    skeleton (list of str)
        Names fo the bones specified in fname.
    cols (str)
        Data columns to keep. Columns are XVQAW (position, vel, quaternion, acc, angular vel)
    """
    from ising.heisenberg import rotate

    df = pd.read_csv(fname,skiprows=5,sep='\t')
    
    # Only keep desired columns.
    keepix = np.zeros((len(df.columns)),dtype=bool)
    for s in cols:
        keepix += np.array([s in c for c in df.columns])
    df = df.ix[:,keepix]
    columns = list(df.columns)

    # Rename numbered columns by body parts.
    skeleton = calc_file_body_parts()
    nameIx = 0
    for i,s in enumerate(skeleton):
        if not 'contact' in s:
            for j,c in enumerate(columns):
                columns[j] = c.replace(str(nameIx+1).zfill(2),s)
            nameIx += 1
    df.columns = columns
    
    # Rotate vectors such that z-axis is along Zd axis.
    with open(fname,'r') as f:
        zd = np.array([float(i) for i in f.readline().split('\t')[1:]])
    n = np.cross(zd,np.array([-1,0,0]))
    theta = np.arccos(zd.dot([-1,0,0]))
    
    for i in xrange(len(df.columns)):
        if any([c+'-x' in df.columns[i] for c in cols]):
            df.ix[:,i:i+3].values[:,:] = rotate(df.ix[:,i:i+3].values,n,theta)
    return df

def load_bvh(fname,includeDisplacement=False,removeBlank=True):
    """
    Load data from BVD file. Euler angles are given as YXZ. Axis Neuron only keeps track of displacement for the hip.
    Details about data files from Axis Neuron?
    2016-11-07

    Params:
    -------
    fname (str)
        Name of file to load
    includeDisplacement (bool=False)
        If displacement data is included for everything including root.
    removeBlank (bool=True)
        Remove entries where nothing changes over the entire recording session. This should mean that there was nothing being recorded in that field.

    Value:
    ------
    df (dataFrame)
    dt (float)
        Frame rate.
    """
    from itertools import chain
    from pyparsing import nestedExpr
    import string

    skeleton = load_skeleton(fname)
    bodyParts = skeleton.nodes

    # Find the line where data starts.
    lineix = 0
    with open(fname) as f:
        f.readline()
        f.readline()
        ln = f.readline()
        lineix += 3
        while not 'MOTION' in ln:
            ln = f.readline()
            lineix += 1
        
        # Read in the frame rate.
        while 'Frame Time' not in ln:
            ln = f.readline()
            lineix += 1
        dt = float( ln.split(' ')[-1] )
    
    # Parse motion.
    df = pd.read_csv(fname,skiprows=lineix+2,delimiter=' ',header=None)
    df = df.iloc[:,:-1]  # remove bad last col
    
    if includeDisplacement:
        df.columns = pd.MultiIndex.from_arrays([list(chain.from_iterable([[b]*6 for b in bodyParts])),
                                            ['xx','yy','zz','y','x','z']*len(bodyParts)])
    else:
        df.columns = pd.MultiIndex.from_arrays([[bodyParts[0]]*6 + 
                                                 list(chain.from_iterable([[b]*3 for b in bodyParts[1:]])),
                                            ['xx','yy','zz']+['y','x','z']*len(bodyParts)])
   

    # Filtering.
    if removeBlank:
        # Only keep entries that change at all.
        df = df.iloc[:,np.diff(df,axis=0).sum(0)!=0] 
    # Units of radians and not degress.
    df *= np.pi/180.
    return df,dt,skeleton

def load_skeleton(fname):
    """
    Load skeleton from BVH file header. 
    2016-11-07

    Params:
    -------
    fname (str)
        Name of file to load
    includeDisplacement (bool=False)
        If displacement data is included for everything including root.
    removeBlank (bool=True)
        Remove entries where nothing changes over the entire recording session. This should mean that there
        was nothing being recorded in that field.

    Value:
    ------
    df (dataFrame)
    dt (float)
        Frame rate.
    """
    from itertools import chain
    from pyparsing import nestedExpr
    import string

    # Parse skeleton.
    # Find the line where data starts and get skeleton tree lines.
    s = ''
    lineix = 0
    bodyParts = ['Hips']  # for keeping track of order of body parts
    with open(fname) as f:
        f.readline()
        f.readline()
        ln = f.readline()
        lineix += 3
        while not 'MOTION' in ln:
            if 'JOINT' in ln:
                bodyParts.append( ''.join(a for a in ln.lstrip(' ').split(' ')[1] if a.isalnum()) )
            s += ln
            ln = f.readline()
            lineix += 1
        
        # Read in the frame rate.
        while 'Frame Time' not in ln:
            ln = f.readline()
            lineix += 1
        dt = float( ln.split(' ')[-1] )
    
    s = nestedExpr('{','}').parseString(s).asList()
    nodes = []

    def parse(parent,thisNode,skeleton):
        """
        Keep track of traversed nodes in nodes list.

        Params:
        -------
        parent (str)
        skeleton (list)
            As returned by pyparsing
        """
        children = []
        for i,ln in enumerate(skeleton):
            if (not type(ln) is list) and 'JOINT' in ln:
                children.append(skeleton[i+1])
            elif type(ln) is list:
                if len(children)>0:
                    parse(thisNode,children[-1],ln)
        nodes.append( Node(thisNode,parents=[parent],children=children) )
    
    # Parse skeleton.
    parse('','Hips',s[0])
    # Resort into order of motion data.
    nodesNames = [n.name for n in nodes]
    bodyPartsIx = [nodesNames.index(n) for n in bodyParts]
    nodes = [nodes[i] for i in bodyPartsIx]
    skeleton = Tree(nodes) 
   
    return skeleton



# ------------------ #
# Class definitions. #
# ------------------ #
class Node(object):
    def __init__(self,name=None,parents=[],children=[]):
        self.name = name
        self.parents = parents
        self.children = children

    def add_child(self,child):
        self.children.append(child)

class Tree(object):
    def __init__(self,nodes):
        self._nodes = nodes
        self.nodes = [n.name for n in nodes]
        names = [n.name for n in nodes]
        if len(np.unique(names))<len(names):
            raise Exception("Nodes have duplicate names.")

        self.adjacency = np.zeros((len(nodes),len(nodes)))
        for i,n in enumerate(nodes):
            for c in n.children:
                try:
                    self.adjacency[i,names.index(c)] = 1
                # automatically insert missing nodes (these should all be dangling)
                except ValueError:
                    self.adjacency = np.pad( self.adjacency, ((0,1),(0,1)), mode='constant', constant_values=0)
                    self._nodes.append( Node(c) )
                    names.append(c)

                    self.adjacency[i,names.index(c)] = 1
        
    def print_tree(self):
        print self.adjacency


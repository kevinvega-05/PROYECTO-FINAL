import sys, os, math
sys.path.insert(0, os.path.join(RAIZ, "")
import numpy as np, pybullet as p
import config_fisico as F
from config import TIPOS
from PIL import Image
MM=0.001
p.connect(p.DIRECT)
def box(cx,cy,cz,sx,sy,sz,col,yaw=0):
    v=p.createVisualShape(p.GEOM_BOX,halfExtents=[sx/2*MM,sy/2*MM,sz/2*MM],rgbaColor=col)
    p.createMultiBody(0,-1,v,basePosition=[cx*MM,cy*MM,cz*MM],baseOrientation=p.getQuaternionFromEuler([0,0,yaw]))
def mesh(f,pos,yaw,col):
    v=p.createVisualShape(p.GEOM_MESH,fileName=f,meshScale=[MM]*3,rgbaColor=col)
    p.createMultiBody(0,-1,v,basePosition=[x*MM for x in pos],baseOrientation=p.getQuaternionFromEuler([0,0,yaw]))
def cyl(cx,cy,z0,r,h,col):
    v=p.createVisualShape(p.GEOM_CYLINDER,radius=r*MM,length=h*MM,rgbaColor=col)
    p.createMultiBody(0,-1,v,basePosition=[cx*MM,cy*MM,(z0+h/2)*MM])
# mesa
box(100,0,-6,900,520,12,[0.80,0.66,0.48,1])
# banda (ultimos 330 mm): franja, panel blanco, patas
Lb=330; W=F.BANDA_ANCHO
box(-Lb/2,0,F.BANDA_Z-2.5,Lb,W-20,5,[0.35,0.37,0.40,1])           # cadena
for s in (-1,1):
    box(-Lb/2,s*(W/2-5),F.BANDA_Z-27,Lb,10,50,[0.95,0.95,0.96,1])  # paneles laterales
for lx in (-30,-150,-290):
    for s in (-1,1): box(lx,s*(W/2-5),15,8,8,30,[0.45,0.47,0.5,1])
# guias
box(-140,W/2-14,F.BANDA_Z+8,60,6,16,[0.55,0.58,0.6,1])
# disco y vasos
yaw=F.yaw_disco_para_llenar(7)   # vaso 7 ($500 actual) en llenado
mesh(os.path.join(RAIZ, "/cad/disco_portavasos.stl",[F.EJE_X,F.EJE_Y,F.DISCO_BASE_Z],yaw,[0.86,0.88,0.90,1])
cols=[(0.75,0.75,0.78),(0.80,0.62,0.35),(0.72,0.72,0.75),(0.78,0.60,0.32),(0.70,0.70,0.73),(0.85,0.75,0.30),(0.68,0.68,0.72),(0.90,0.78,0.25),(0.95,0.80,0.20)]
vcol=[(0.20,0.60,0.86),(0.90,0.49,0.13),(0.15,0.68,0.38),(0.91,0.30,0.24),(0.61,0.35,0.71),(0.10,0.74,0.61),(0.95,0.77,0.06),(0.20,0.29,0.37),(0.83,0.33,0.00)]
for k in range(9):
    x,y=F.pos_vaso(k,yaw)
    c=vcol[k]; mesh(os.path.join(RAIZ, "/cad/vaso.stl",[x,y,F.VASO_TOPE_Z-F.VASO_H],0,[c[0],c[1],c[2],1])
    # monedas apiladas visibles dentro
    r=TIPOS[k]["diam_mm"]/2
    for i in range(3+k%3):
        cyl(x+0.5*(i%2),y,F.VASO_TOPE_Z-F.VASO_H+F.VASO_FONDO+i*2.5,r,2.2,[*cols[k],1])
# moneda cayendo y moneda en la banda
cyl(F.DIST_BORDE_A_VASO-2,0,F.VASO_TOPE_Z+4,TIPOS[7]["diam_mm"]/2,2.2,[0.95,0.8,0.25,1])
cyl(-40,0,F.BANDA_Z,TIPOS[7]["diam_mm"]/2,2.2,[0.95,0.8,0.25,1])
# motor (28BYJ-48) bajo el disco y eje
cyl(F.EJE_X,0,-10,14,19,[0.7,0.72,0.75,1])
cyl(F.EJE_X,0,0,2.5,F.DISCO_BASE_Z,[0.3,0.3,0.3,1])
def shot(eye,tgt,w,h,fn,fov=38):
    vm=p.computeViewMatrix(eye,tgt,[0,0,1]); pm=p.computeProjectionMatrixFOV(fov,w/h,0.01,3)
    img=p.getCameraImage(w,h,vm,pm,renderer=p.ER_TINY_RENDERER,shadow=1,lightDirection=[-0.4,-0.6,1.0],lightColor=[1,1,1])
    Image.fromarray(np.reshape(img[2],(h,w,4))[:,:,:3].astype(np.uint8)).save(fn)
out=sys.argv[1]
t=[0.07,0.0,0.04]
shot([0.33,-0.26,0.21],[0.03,0.0,0.05],1400,900,out+"/a.png",fov=42)
shot([0.05,-0.58,0.12],[0.08,0.0,0.05],1400,900,out+"/b.png",fov=40)
shot([0.05,-0.001,0.55],[0.05,0.0,0.0],1400,900,out+"/c.png",fov=36)

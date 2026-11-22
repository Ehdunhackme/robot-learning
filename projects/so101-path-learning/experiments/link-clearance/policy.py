"""Portable inference for the trained path ranker."""
import numpy as np


def features(tasks, recipe):
    tasks = np.atleast_2d(tasks).astype(np.float32)
    x = tasks[:, :18]
    if recipe in ("relative","skeleton"):
        a,b,center,size = x[:, :6],x[:, 6:12],x[:, 12:15],x[:,15:18]
        radius = np.hypot(center[:,0]-.0388353,center[:,1])
        bearing = np.arctan2(-center[:,1],center[:,0]-.0388353)
        span = b[:,0]-a[:,0]
        fraction = np.clip((bearing-a[:,0])/np.where(abs(span)>.01,span,1),0,1)
        between = a + fraction[:,None]*(b-a)
        x=np.column_stack([x,radius,bearing,fraction,between[:,1:4],center[:,2]-size[:,2],center[:,2]+size[:,2]])
    if recipe=="skeleton":
        from kinematics import sparse_features
        x=np.column_stack([x,sparse_features(tasks)])
    return x.astype(np.float32)


def predict(model,tasks):
    x=(features(tasks,str(model["recipe"]))-model["mean"])/model["scale"]
    for i in range(int(model["layers"])):
        x=x@model[f"w{i}"]+model[f"b{i}"]
        if i+1<int(model["layers"]):
            x=np.maximum(x,0)
    return x.argmin(1)


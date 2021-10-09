import numpy as np

def linear(p_fin, p_ini):
    return (p_fin/p_ini) - 1

def log(p_fin, p_ini):
    return np.log(p_fin / p_ini)


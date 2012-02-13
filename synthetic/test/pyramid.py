'''
Created on Jan 25, 2012

@author: tobibaum
'''

import numpy as np
import scipy.io as sio
from os.path import join

import synthetic.config as config
from synthetic.pyramid import *


def create_grid():
  positions = np.zeros((25,2))
  ind = 0
  for x in range(5):
    for y in range(5):
      positions[ind,:] = [x, y]
      ind+=1
  return positions

def test_get_indices():
  positions = create_grid()        
  inds = get_indices_for_pos(positions, .1, 3.5, .5, 3)
  inds_gt = np.array([6,7,8,11,12,13,16,17,18])  
  assert(inds.all() == inds_gt.all())

def test_get_indices_empty_result():
  positions = create_grid()
  inds = get_indices_for_pos(positions, .1, 3.5, .5, .9)  
  assert(inds.size == 0)       
  
def test_compare_to_original_pyramid():
  spatial_pyr_root = join(config.test_support_dir, 'pyramid/')
  mdict = {}
  io.loadmat(spatial_pyr_root + 'p1010843_texton_ind_200.mat', mdict)
  data = mdict['texton_ind'][0][0][0]
  x = mdict['texton_ind'][0][0][1]
  y = mdict['texton_ind'][0][0][2]
  ass = np.hstack((x,y,data))
  image = Image()
  image.size = (640,480)
  
  L = 2
  codebook = np.zeros((200,6))
  pyr = extract_pyramid(L, ass[:,0:2], ass, codebook, image)
  mat = sio.loadmat(join(spatial_pyr_root,'p1010843_pyramid_200_3.mat'))['pyramid']
  
  assert (mat.all() == pyr.all())
#  io.savemat(spatial_pyr_root + 'python_pyr.mat', {'pyr':pyr})
  
if __name__=='__main__':  
  test_get_indices()
  test_get_indices_empty_result()
  test_compare_to_original_pyramid()
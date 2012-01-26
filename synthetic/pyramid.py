""" Lazebnik's Spatial Pyramid Matching
@author: Tobias Baumgartner
@contact: tobi.baum@gmail.com
@date: 10/27/11
"""

import numpy as np
import os
from synthetic.dataset import Dataset
import scipy.cluster.vq as sp
from collections import Counter
from numpy.ma.core import floor
from scipy import io 
from synthetic.image import Image


def get_indices_for_pos(positions, xmin, xmax, ymin, ymax):
  indices = np.matrix(np.arange(positions.shape[0]))
  indices = indices.reshape(positions.shape[0], 1)
  positions = np.asarray(np.hstack((positions, indices)))
  if not positions.size == 0:  
    positions = positions[positions[:, 0] >= xmin, :]
  if not positions.size == 0:
    positions = positions[positions[:, 0] <= xmax, :]
  if not positions.size == 0:  
    positions = positions[positions[:, 1] >= ymin, :]
  if not positions.size == 0:
    positions = positions[positions[:, 1] <= ymax, :]
  #print 'positio', positions
  return np.asarray(positions[:, 2], dtype='int32')

# This code should be in Extractor!
def extract_pyramid(L, positions, assignments, codebook, image):
  im_width = image.size[0]
  im_height = image.size[1]
  num_bins = 2**  L
  histogram_levels = []
  M = codebook.shape[0]
  histogram_level = np.zeros((num_bins,num_bins,M))
  #finest level
  for i in range(num_bins):
    for j in range(num_bins):
      xmin = floor(im_width / num_bins * i)
      xmax = floor(im_width / num_bins * (i + 1))
      ymin = floor(im_height / num_bins * j)
      ymax = floor(im_height / num_bins * (j + 1))
      indices = get_indices_for_pos(positions, xmin, xmax, ymin, ymax)
      if indices.size == 0:
        bin_ass = np.matrix([])
      else:
        bin_ass = assignments[indices][:,2]
      bin_ass = bin_ass.reshape(1,bin_ass.size)[0]
      counts = Counter(bin_ass)
      histogram = [counts.get(x,0) for x in range(codebook.shape[0])]
      if not len(bin_ass) == 0:
        histogram_level[i,j,:] = np.divide(histogram,float(assignments.shape[0]))
      else:
        histogram_level[i,j,:] = histogram
  histogram_levels.append(histogram_level)
  
  # the other levels (just sum over lower levels respectively)  
  for level in range(L):
    num_bins = num_bins/2  
    level = level + 1
    lower_histogram = histogram_levels[level - 1]
    histogram_level = np.zeros((num_bins,num_bins,M))  
    for i in range(num_bins):
      for j in range(num_bins):
        histogram_level[i,j,:] = lower_histogram[2*i,2*j + 1,:] + \
          lower_histogram[2*i + 1,2*j,:] + lower_histogram[2*i,2*j,:] + \
          lower_histogram[2*i + 1,2*j + 1,:]
    histogram_levels.append(histogram_level)
    
  pyramid = []
  num_bins = 2**L
  for lev in range(L+1):
    if lev == L:
      power = -L
    else:
      power = -lev-1
    for m in range(M):
      for j in range(num_bins):         
        for i in range(num_bins):         
          pyramid.append(histogram_levels[lev][i,j,m]*2**(power))
    num_bins = num_bins/2
  pyramid = np.matrix(pyramid)
  return pyramid

from synthetic.extractor import Extractor
if __name__=='__main__':
  # Load codebook and
  spatial_pyr_root = '/home/tobibaum/Documents/Vision/research/SpatialPyramid/data2/'
  mdict = {}
  io.loadmat(spatial_pyr_root + 'p1010843_hist_200.mat', mdict)
  thehist = mdict['H']
  io.loadmat(spatial_pyr_root + 'p1010843_texton_ind_200.mat', mdict)
  data = mdict['texton_ind'][0][0][0]
  x = mdict['texton_ind'][0][0][1]
  y = mdict['texton_ind'][0][0][2]
  ass = np.hstack((x,y,data))
  image = Image()
  image.size = (640,480)
  
  
  cls = 'dog'
  d = Dataset('full_pascal_val')
  e = Extractor()
  pos_images = d.get_pos_samples_for_class(cls) 
  codebook_file = "/home/tobibaum/Documents/Vision/data/features/dsift/codebooks/dog_15_200"
  #codebook = np.loadtxt(codebook_file) 
  L = 2
  codebook = np.zeros((200,6))
  pyr = extract_pyramid(L, ass[:,0:2], ass, codebook, image)
  print pyr
  io.savemat(spatial_pyr_root + 'python_pyr.mat', {'pyr':pyr})
#  for img_idx in pos_images:
#    image = d.images[img_idx.astype('int32')]
#    assignments = e.get_assignments(np.matrix([[0,0],[1000,1000]]),'dsift',codebook,cls,image)
#    pyr = extract_pyramid(L, assignments[0:2],assignments, codebook, image)
#    print pyr
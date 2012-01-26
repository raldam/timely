'''
Created on Nov 16, 2011

@author: Tobias Baumgartner
'''

from common_imports import *

from synthetic.classifier import Classifier
import synthetic.config as config
from synthetic.training import load_svm
from synthetic.dataset import Dataset

class DPMClassifier(Classifier):
  def __init__(self):
    self.name = 'dpm'
    
  def create_vector(self, feats, cls, img, intervalls, lower, upper):
    if feats.arr.size == 0:
      return np.zeros((1,intervalls+1))
    dpm = feats.subset(['score', 'cls_ind', 'img_ind'])
    img_dpm = dpm.filter_on_column('img_ind', img, omit=True)
    if img_dpm.arr.size == 0:
      print 'empty vector'
      return np.zeros((1,intervalls+1))
    cls_dpm = img_dpm.filter_on_column('cls_ind', cls, omit=True)
    hist = self.compute_histogram(cls_dpm.arr, intervalls, lower, upper)
    vector = np.zeros((1, intervalls+1))
    vector[0,0:-1] = hist
    vector[0,-1] = img_dpm.shape()[0]
    return vector
  
if __name__=='__main__':
  train_set = 'full_pascal_train'
  train_dataset = Dataset(train_set)  
  dpm_dir = os.path.join(config.res_dir, 'dpm_dets')
  filename = os.path.join(dpm_dir, train_set + '_dets_all_may25_DP.npy')
  dpm_train = np.load(filename)
  dpm_train = dpm_train[()]  
  dpm_train = dpm_train.subset(['score', 'cls_ind', 'img_ind'])
  dpm_classif = DPMClassifier()
  dpm_train.arr = dpm_classif.normalize_scores(dpm_train.arr)
  
  val_set = 'full_pascal_val'
  test_dataset = Dataset(val_set)  
  dpm_test_dir = os.path.join(config.res_dir, 'dpm_dets')
  filename = os.path.join(dpm_dir, val_set + '_dets_all_may25_DP.npy')
  dpm_test = np.load(filename)
  dpm_test = dpm_test[()]  
  dpm_test = dpm_test.subset(['score', 'cls_ind', 'img_ind'])
  dpm_test.arr = dpm_classif.normalize_scores(dpm_test.arr) 
  
  lowers = [0.,0.2,0.4]
  uppers = [1.,0.8,0.6]
  kernels = ['linear', 'rbf']
  intervallss = [10, 20, 50]
  clss = range(20)
  Cs = [2.5,3.]  
  list_of_parameters = [lowers, uppers, kernels, intervallss, clss, Cs]
  product_of_parameters = list(itertools.product(*list_of_parameters))
  
  for params_idx in range(comm_rank, len(product_of_parameters), comm_size):
    params = product_of_parameters[params_idx] 
    lower = params[0]
    upper = params[1]
    kernel = params[2]
    intervalls = params[3]
    cls_idx = params[4]
    C = params[5]
    dpm_classif.train_for_all_cls(train_dataset, dpm_train,intervalls,kernel, lower, upper, cls_idx, C)
    dpm_classif.test_svm(test_dataset, dpm_test, intervalls,kernel, lower, upper, cls_idx, C)
  
  
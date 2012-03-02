from common_imports import *
from common_mpi import *
import synthetic.config as config
from IPython import embed

from synthetic.classifier import Classifier
from synthetic.dataset import Dataset
from synthetic.training import svm_predict, svm_proba
#import synthetic.config as config
from synthetic.config import get_ext_dets_filename
from synthetic.image import Image
from synthetic.util import Table
#from synthetic.dpm_classifier import create_vector

class CSCClassifier(Classifier):
  def __init__(self, suffix, cls, dataset, num_bins=5):
    self.name = 'csc'
    self.suffix = suffix
    self.cls = cls
    self.dataset = dataset
    self.svm = self.load_svm()
    self.num_bins = num_bins
    
    self.bounds = self.load_bounds()
    
  def classify_image(self, img, dets=None):
    result = self.get_score(img, dets=dets, probab=True)    
    return result
    
  def get_score(self, img, dets=None, probab=True):
    """
    with probab=True returns score as a probability [0,1] for this class
    without it, returns result of older svm
    """
    if not isinstance(img, Image):
      image = self.dataset.images[img]
    else:
      image = img
      img = self.dataset.images.index(img)
    if not dets:
      vector = self.get_vector(img)
    else:
      vector = self.create_vector_from_dets(dets,img)
    
    if probab:
      return svm_proba(vector, self.svm)[0][1]
    return svm_predict(vector, self.svm)[0,0]
  
  def create_vector_from_dets(self, dets, img, bounds=None):
    if 'cls_ind' in dets.cols:
      dets = dets.filter_on_column('cls_ind', self.dataset.classes.index(self.cls), omit=True)
    
    if bounds == None:
      bounds = self.bounds
    dets = dets.subset(['score', 'img_ind'])
    #dets.arr = self.normalize_dpm_scores(dets.arr)
    
    # TODO from sergeyk: what is .size? Be specific and use .shape[0] or .shape[1]
    if dets.arr.size == 0:
      return np.zeros((1,self.num_bins))

    img_dpm = dets.filter_on_column('img_ind', img, omit=True)

    if img_dpm.arr.size == 0:
      #print 'empty vector'
      return np.zeros((1,self.num_bins))
    bins = ut.determine_bin(img_dpm.arr.T[0], bounds)
    hist = ut.histogram_just_count(bins, self.num_bins, normalize=True)
    
    return hist
     
  def get_vector(self, img):
    image = self.dataset.images[img]  
    filename = os.path.join(config.get_ext_dets_vector_foldname(self.dataset),image.name[:-4])
    if os.path.exists(filename):
      return np.load(filename)[()]
    else:
      vector = self.create_vector(img)
      np.save(filename, vector)
      return vector
    
  def create_vector(self, img):
    filename = config.get_ext_dets_filename(self.dataset, 'csc_'+self.suffix)
    csc_test = np.load(filename)
    feats = csc_test[()]
    return self.create_vector_from_dets(feats, img)    
  
  def get_all_vectors(self):
    for img_idx in range(comm_rank, len(self.dataset.images), comm_size):
      print 'on %d get vect %d/%d'%(comm_rank, img_idx, len(self.dataset.images))
      self.get_vector(img_idx)
      
  def csc_classifier_train(self, parameters, suffix, dets, train_dataset, probab=True, test=True, force_new=False):      
    kernels = ['linear', 'rbf', 'chi2']       
    for params_idx in range(comm_rank, len(parameters), comm_size):
      params = parameters[params_idx] 
      
      kernel = params[2]
      if not type(kernel) == type(''):
        kernel = kernels[int(kernel)]
      
      C = params[5]
      
      print kernel, C

      filename = config.get_classifier_svm_learning_filename(self.csc_classif, self.cls, kernel, C)
      
      if not os.path.isfile(filename) or force_new:
        bounds = ut.importance_sample(dets.subset(['score']).arr, self.num_bins+1)
        self.store_bounds(bounds)

        self.train_for_cls(train_dataset, dets, kernel, self.cls, C, probab=probab)
        if test:
          #self.test_svm(val_dataset, csc_test, kernel, cls_idx, C)
          None  

  def csc_classifier_train_all_params(self,suffix):
    lowers = [0.]#,0.2,0.4]
    uppers = [1.,0.8,0.6]
    kernels = ['linear']#, 'rbf']
    intervallss = [10, 20, 50]
    clss = range(20)
    Cs = [1., 1.5, 2., 2.5, 3.]  
    list_of_parameters = [lowers, uppers, kernels, intervallss, clss, Cs]
    product_of_parameters = list(itertools.product(*list_of_parameters))  
    self.csc_classifier_train(product_of_parameters)
  
def old_training_stuff(): 
  test_set = 'full_pascal_test'
  for suffix in ['half']:#,'default']:
    test_dataset = Dataset(test_set)  
    filename = config.get_ext_dets_filename(test_dataset, 'csc_'+suffix)
    csc_test = np.load(filename)
    csc_test = csc_test[()]  
    csc_test = csc_test.subset(['score', 'cls_ind', 'img_ind'])
    score = csc_test.subset(['score']).arr
    csc_classif = CSCClassifier(suffix)
    csc_test.arr = csc_classif.normalize_dpm_scores(csc_test.arr)
    
    classes = config.pascal_classes
    
    best_table = csc_classif.get_best_table()
    
    svm_save_dir = os.path.join(config.res_dir,csc_classif.name)+ '_svm_'+csc_classif.suffix+'/'
    score_file = os.path.join(svm_save_dir,'test_accuracy.txt')
                      
    for cls_idx in range(comm_rank, 20, comm_size):
      row = best_table.filter_on_column('cls_ind', cls_idx).arr
      intervals = row[0,best_table.cols.index('bins')]
      kernel = config.kernels[int(row[0,best_table.cols.index('kernel')])]
      lower = row[0,best_table.cols.index('lower')]
      upper = row[0,best_table.cols.index('upper')]
      C = row[0,best_table.cols.index('C')]
      acc = csc_classif.test_svm(test_dataset, csc_test, intervals,kernel, lower, \
                                 upper, cls_idx, C, file_out=False, local=True)
      print acc
      with open(score_file, 'a') as myfile:
          myfile.write(classes[cls_idx] + ' ' + str(acc) + '\n')

def get_best_parameters():
  parameters = []
  d = Dataset('full_pascal_trainval')
  
  # this is just a dummy, we don't really need it, just to read best vals
  csc = CSCClassifier('default', 'dog', d)
  best_table = csc.get_best_table()
  for row_idx in range(best_table.shape()[0]):
    row = best_table.arr[row_idx, :]
    params = []
    for idx in ['lower', 'upper', 'kernel', 'bins', 'cls_ind', 'C']:
      params.append(row[best_table.ind(idx)])
    parameters.append(params)
  return parameters

def classify_all_images(d, force_new=False):
  suffix = 'default'
  tt = ut.TicToc()
  tt.tic()
  print 'start classifying all images on %d...'%comm_rank
  table = np.zeros((len(d.images), len(d.classes)))
  i = 0
  for cls_idx, cls in enumerate(d.classes):
    csc = CSCClassifier(suffix, cls, d)
    for img_idx in range(comm_rank, len(d.images), comm_size):    
      if i == 5:
        print 'image %d on %d/%d'%(comm_rank, 20*i, 20*len(d.images)/comm_size)  
        i = 0
      i += 1  
      
      score = csc.get_score(img_idx, probab=True)
      table[img_idx, cls_idx] = score
              
  dirname = ut.makedirs(os.path.join(config.get_ext_dets_foldname(d), 'agent_wise'))
  filename = os.path.join(dirname,'table_%d'%comm_rank)
  np.savetxt(filename, table)
            
  print 'Classified all images in %f secs on %d'%(tt.toc(quiet=True), comm_rank)
  
def compile_table_from_classifications(d):  
  errors = 0
  table = np.zeros((len(d.images), len(d.classes)))
  dirname = ut.makedirs(os.path.join(config.get_ext_dets_foldname(d), 'agent_wise'))
  
  for i in range(comm_size):
    filename = os.path.join(dirname,'table_%d'%i)
    table += np.loadtxt(filename)
  dirname = ut.makedirs(os.path.join(config.get_ext_dets_foldname(d)))
  filename = os.path.join(dirname,'table')
  np.savetxt(filename, table)
    
  print 'errors: %d'%errors
  return table

def create_csc_stuff(d, classify_images=True, force_new=False):
        
  dirname = ut.makedirs(os.path.join(config.get_ext_dets_foldname(d)))
  print dirname
  filename = os.path.join(dirname,'table')
  
  if not os.path.exists(filename):
    if classify_images:
      classify_all_images(d, force_new=force_new)

    safebarrier(comm)    
    table = compile_table_from_classifications(d)
    
    if comm_rank == 0:      
      print 'save table as %s'%filename
      
      csc_table = Table()
      csc_table.cols = d.classes + ['img_ind']
      csc_table.arr = np.hstack((table, np.array(np.arange(table.shape[0]),ndmin=2).T))      
      print csc_table
      cPickle.dump(csc_table, filename)                 

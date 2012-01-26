from sklearn.cross_validation import KFold

from common_imports import *
from common_mpi import *

from synthetic.class_priors import NGramModel
import synthetic.util as ut
import synthetic.config as config
from synthetic.detector import Detector
from synthetic.image import Image
from synthetic.training import *

class GistPriors():
  """
  Compute a likelihood-vector for the classes given a (precomputed) gist detection
  """
  def __init__(self, dataset_name):
    """
    Load all gist features right away
    """
    print("Started loading GIST")
    t = time.time()
    self.gist_table = np.load(config.get_gist_dict_filename(dataset_name))
    print("Time spent loading gist: %.3f"%(time.time()-t))
    self.svms = self.load_all_svms()
    self.dataset = Dataset(dataset_name)
        
  def load_all_svms(self):
    svms = {}
    for cls in config.pascal_classes:
      if os.path.exists(config.get_gist_svm_filename(cls)):
        svms[cls] = load_svm(config.get_gist_svm_filename(cls))
      else:
        print 'gist svm for',cls,'does not exist'
    return svms
    
  def get_proba_for_cls(self, cls, img):
    image = self.dataset.get_image_by_filename(img.name)
    index = self.dataset.get_img_ind(image)
    gist = self.gist_table[index] 
    return svm_proba(gist, self.svms[cls])
         
  def get_priors(self, img):
    num_classes = len(config.pascal_classes)
    prior_vect = []
    for cls_idx in range(num_classes):
      cls = config.pascal_classes[cls_idx]
      prob = self.get_proba_for_cls(cls, img)[0,1]
      prior_vect.append(prob)      
    return prior_vect
  
  def get_priors_lam(self, img, prior, lam=0.95):
    gist = self.get_priors(img)
    prior = np.array(prior)
    gist = np.array(gist)
    comb = lam*prior + (1-lam)*gist
    return comb
  
  def compute_obj_func(self, gist, truth):
    diff = gist - truth
    sqr = np.multiply(diff,diff)
    sqrsum = np.sum(sqr)
    return sqrsum
  
  def get_gists_for_imgs(self, imgs, dataset):
    images = dataset.images
    num = imgs.size
    print num
    gist = np.zeros((num, 960))
    ind = 0    
    for img in imgs:
      image = dataset.get_image_by_filename(images[img].name)
      index = dataset.get_img_ind(image)
      gist[ind] = self.gist_table[index]
      ind += 1
    return gist
  
  def train_all_svms(self, dataset,C=1.0):
    """
    Train classifiers to 
    """
    for cls in config.pascal_classes:
      print 'train class', cls
      t = time.time()
      pos = dataset.get_pos_samples_for_class(cls)
      num_pos = pos.size
      neg = dataset.get_neg_samples_for_class(cls)
      neg = np.random.permutation(neg)[:num_pos]
      print '\tload pos gists'
      pos_gist = self.get_gists_for_imgs(pos, dataset)
      print '\tload neg gists'       
      neg_gist = self.get_gists_for_imgs(neg, dataset)
      x = np.concatenate((pos_gist, neg_gist))
      y = [1]*num_pos + [-1]*num_pos
      print '\tcompute svm'
      svm = train_svm(x, y, kernel='linear',C=C,probab=True)
      svm_filename = config.get_gist_svm_filename(cls)+'_'+str(C)
      save_svm(svm, svm_filename)     
      print '\ttook', time.time()-t,'sec'

  def evaluate_svm(self, cls, dataset, C):
    svm_filename = config.get_gist_svm_filename(cls)+'_'+str(C)
    svm = load_svm(svm_filename)
    print 'evaluate class', cls
    t = time.time()
    pos = dataset.get_pos_samples_for_class(cls)
    num_pos = pos.size 
    neg = dataset.get_neg_samples_for_class(cls)
    neg = np.random.permutation(neg)[:num_pos]
    print '\tload pos gists'
    pos_gist = self.get_gists_for_imgs(pos, dataset)
    print '\tload neg gists'       
    neg_gist = self.get_gists_for_imgs(neg, dataset)
    x = np.concatenate((pos_gist, neg_gist))
    y = [1]*num_pos + [-1]*num_pos
    result = svm_predict(x, svm)
    test_classification = np.matrix([1]*pos_gist.shape[0] + [-1]*neg_gist.shape[0]).reshape((result.shape[0],1))  
    acc = sum(np.multiply(result,test_classification) > 0)/float(2.*num_pos)
    outfile_name = os.path.join(config.gist_dir, cls)
    outfile = open(outfile_name,'a')
    outfile.writelines(str(C) + ' ' + str(acc[0][0])+'\n') 
    
  def cross_val_lambda(self, lam):
    images = self.dataset.images
    num_folds = 4
    loo = KFold(len(images), num_folds)
    errors = []
    fold_num = 0
    for train,val in loo:
      print 'compute error for fold', fold_num
      indices = np.arange(len(images))[train]
      print len(indices)
      data = np.zeros((indices.size,20))
      ind = 0
      for idx in indices:
        data[ind] = images[idx].get_cls_counts()
        ind += 1        
      model = NGramModel(data)
      priors = model.get_probabilities()
      error = 0
      indices = np.arange(len(images))[val]
       
      for idx in indices:
        img = images[idx]
        print 'evaluate img', img.name
        t = time.time()
        gist = self.get_priors_lam(img,  priors, lam)
        t = time.time() - t
        print 'gist took %f secs'%t
        error += self.compute_obj_func(gist, img.get_cls_counts()>0)
      error = error/indices.shape[0]
      
      errors.append(error)
      print 'error:', error
    avg_error = sum(errors)/4
    return avg_error
    
    
def gist_evaluate_best_svm():
  train_d = Dataset('full_pascal_train')
  train_dect = GistPriors(train_d.name)
  val_d = Dataset('full_pascal_val')
  val_dect = GistPriors(val_d.name)  
  
  ranges = np.arange(0.5,10.,0.5)
  for C_idx in range(mpi_rank, len(ranges), mpi_size):
    C = ranges[C_idx] 
    train_dect.train_all_svms(train_d, C)
    for cls in config.pascal_classes:
      val_dect.evaluate_svm(cls, val_d, C)
    
def test_gist_one_sample(dataset):    
  dect = GistPriors(dataset)
  d = Dataset(dataset)
  vect = dect.get_priors(d.images[1])
  for idx in range(len(vect)):
    if vect[idx] > 0.5:
     print config.pascal_classes[idx], vect[idx]
     
def save_gist_differently():
  gist_dict = cPickle.load(open(config.res_dir+'gist_features/features','r'))
  for dataset in ['full_pascal_train','full_pascal_val','full_pascal_test']:
    d = Dataset(dataset)
    print 'converting set', dataset
    save_file = config.res_dir+'gist_features/'+dataset
    images = d.images
    gist_tab = np.zeros((len(images), 960))
    for idx in range(len(images)):
      img = images[idx]
      print 'on \t', img.name
      gist_tab[idx,:] = gist_dict[img.name[:-3]]
    np.save(save_file, gist_tab)
  
if __name__=='__main__':
  #save_gist_differently()
  #test_gist_one_sample('full_pascal_test')
  #gist_evaluate_best_svm()
  dect = GistPriors('full_pascal_trainval')
  lams = np.arange(0,1,0.025)
  errors = np.zeros((lams.shape[0],1))
  for idx in range(mpi_rank, len(lams),mpi_size):
    lam = lams[idx]
    err = dect.cross_val_lambda(lam)
    errors[idx, 0] = err
  errors = comm.reduce(errors)
  
  if mpi_rank == 0:
    result_file = config.res_dir + 'cross_val_lam_gist.txt'
    outfile = open(result_file,'w')
    print errors
    for idx in range(lams.shape[0]):
      outfile.write(str(lams[idx]) + ' ' + str(errors[idx]) + '\n')    
    outfile.close() 
    
  
  
  
  
  
  
  
  
  
  
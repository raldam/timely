from abc import abstractmethod
import fnmatch

import synthetic.config as config
from common_imports import *
from common_mpi import *
import synthetic.config as config
from pylab import *

from sklearn.svm import SVC, LinearSVC

from synthetic.training import train_svm, svm_predict, save_svm, load_svm,\
  svm_proba
from synthetic.evaluation import Evaluation

class Classifier(object):
  def __init__(self):
    self.name = ''
    self.suffix = ''
    self.cls = ''
    self.tt = ut.TicToc()
    self.bounds = self.load_bounds()
    
  def load_bounds(self):
    filename = config.get_classifier_bounds(self, self.cls)
    if not os.path.exists(filename):
      print 'bounds for %s and class %s dont exist yet'%(self.name, self.cls)
      return None
    bounds = np.loadtxt(filename)
    return bounds
  
  def store_bounds(self, bounds):
    filename = config.get_classifier_bounds(self, self.cls)
    np.savetxt(filename, bounds)
  
  def compute_histogram(self, arr, intervals, lower, upper):
    band = upper - lower
    int_width = band/intervals
    hist = np.zeros((intervals,1))
    # first compute the cumulative  histogram
    for i in range(int(intervals)):
      every = sum(arr < (lower + int_width*(i+1)))
      hist[i] =  every
    # and then uncumulate
    for j in range(int(intervals)-1):
      hist[intervals-j-1] -= hist[intervals-j-2]
    if sum(hist) > 0:
      hist = np.divide(hist, sum(hist)) 
    return np.transpose(hist)
  
#  @abstractmethod
#  def create_vector(self, img):
#    "Create the feature vector."
#    # implement in subclasses
  
  def train(self, pos, neg, kernel, C, probab=True):    
    y = [1]*pos.shape[0] + [-1]*neg.shape[0]
    x = np.concatenate((pos,neg))
    model = train_svm(x, y, kernel=kernel, C=C, probab=probab)
    return model
  
  def evaluate(self, pos, neg, model):
    test_set = np.concatenate((pos,neg))
    test_classification = np.matrix([1]*pos.shape[0] + [-1]*neg.shape[0]).reshape((test_set.shape[0],1))  
    result = svm_predict(test_set, model)
     
    return np.multiply(result,test_classification)
        
  def normalize_dpm_scores(self, arr):     
    # TODO from sergeyk: this is silly, this method should take a 1-d array and return the transformed array
    # why are you relying on scores being in a specific column?
    arr[:, 0:1] = np.power(np.exp(-2.*arr[:,0:1])+1,-1)
    return arr
      
  def train_for_cls(self, train_dataset, val_dataset, dets, kernel, C, probab=True, vtype='hist'):
    cls = self.cls
    filename = config.get_classifier_svm_learning_filename(self,cls,kernel,C, self.num_bins)

    pos_imgs = train_dataset.get_pos_samples_for_class(cls)
    neg_imgs = train_dataset.get_neg_samples_for_class(cls, number=len(pos_imgs))
    pos = []
    neg = []    
      
    dets_arr = dets.subset(['score']).arr
    dets_arr = self.normalize_dpm_scores(dets_arr)
    #bounds = ut.importance_sample(dets_arr, self.num_bins+1)
    bounds = np.linspace(np.min(dets_arr), np.max(dets_arr), self.num_bins+1)
    self.bounds = bounds
    self.store_bounds(bounds)
    
    print comm_rank, 'trains', cls
    pos_det_scores = []
    for idx, img_idx in enumerate(pos_imgs):
      image = train_dataset.images[img_idx]
      vector = self.create_vector_from_dets(dets, image, vtype, bounds)
      scores = dets.filter_on_column('img_ind',img_idx).subset_arr('score')
      #scores = np.power(np.exp(-2.*scores)+1,-1)
      pos_det_scores.append(scores)
      print 'load image %d/%d on %d'%(idx, len(pos_imgs), comm_rank)
      pos.append(vector)      
    pos_det_scores = np.concatenate(pos_det_scores)

    neg_det_scores = []
    for idx, img_idx in enumerate(neg_imgs):
      image = train_dataset.images[img_idx]
      vector = self.create_vector_from_dets(dets, image, vtype, bounds)
      scores = dets.filter_on_column('img_ind',img_idx).subset_arr('score')
      #scores = np.power(np.exp(-2.*scores)+1,-1)
      neg_det_scores.append(scores)
      print 'load image %d/%d on %d'%(idx, len(neg_imgs), comm_rank)
      neg.append(vector)
    neg_det_scores = np.concatenate(neg_det_scores)
    
    pos = np.concatenate(pos)
    neg = np.concatenate(neg)
    
    print '%d trains the model for'%comm_rank, cls
    x = np.concatenate((pos, neg))
    y = [1]*pos.shape[0] + [-1]*neg.shape[0]
    #model = self.train(pos, neg, kernel, C, probab=probab)

    model = SVC(kernel='linear', C=1000, probability=True)
    model.fit(x, y)#, class_weight='auto')
    print("model.score(C=1000)")
    print model.score(x,y)

    model = SVC(kernel='linear', C=100, probability=True)
    model.fit(x, y)#, class_weight='auto')
    print("model.score(C=100)")
    print model.score(x,y)

    model = SVC(kernel='linear', C=1, probability=True)
    model.fit(x, y)#, class_weight='auto')
    print("model.score(C=1)")
    print model.score(x,y)
    
    table_t = svm_proba(x, model)
    
    y2 = np.array(y)    
    y2 = (y2+1)/2    
    ap,rec,prec=Evaluation.compute_cls_pr(table_t[:,1], y2)
    print ap
    #pcolor(vstack((model.predict_proba(x)[:,1],y2)));show()
    
#    embed()

    save_svm(model, filename)
  
    # TODO
    #prob3.append(self.classify_image(img, dets, probab=probab, vtype=vtype))
    #pcolor(np.array(np.vstack((pos,neg)))); show()

    
    # Classify on val set
    self.svm = model
    print 'evaluate svm'
    table_cls = np.zeros((len(val_dataset.images), 1))
    for idx, image in enumerate(val_dataset.images):
      print '%d eval on img %d/%d'%(comm_rank, idx, len(val_dataset.images))
      score = self.classify_image(image, dets, probab=probab, vtype=vtype)
      table_cls[img_idx, 0] = score
      
    #print Evaluation.compute_cls_pr(prob3, y)          
#    y = val_dataset.get_cls_ground_truth().subset(cls).arr
#    acc = np.count_nonzero(table_cls == np.array(y,ndmin=2).T)/float(y.shape[0])
#    embed()    
    return table_cls
    
  def get_observation(self, image):
    """
    Get the score for given image.
    """
    observation = {}
    self.tt.tic()
    score = self.get_score(image)
    
    observation['score'] = score
    observation['dt'] = self.tt.toc(quiet=True)    
    return observation 
        
  @abstractmethod
  def get_score(self, img): 
    """
    Get the score for the given image.
    """
  
  def load_svm(self, filename=None):
    if not filename:
      svm_file = config.get_classifier_filename(self,self.cls)
    else:
      svm_file = filename
    print svm_file
    if not os.path.exists(svm_file):
      #raise RuntimeWarning("Svm %s is not trained"%svm_file)
      return None
    else:  
      model = load_svm(svm_file)
      return model
  
  def test_svm(self, test_dataset, feats, intervals, kernel, lower, upper, \
               cls_idx, C, file_out=True,local=False):
    images = test_dataset.images  
  
    cls = test_dataset.classes[cls_idx]
    pos_images = test_dataset.get_pos_samples_for_class(cls)
    pos = []
    neg = []
    print comm_rank, 'evaluates', cls, intervals, kernel, lower, upper, C
    for img in range(len(images)):
      vector = self.create_vector(feats, test_dataset.classes.index(cls), img, intervals, lower, upper)
      if img in pos_images:
        pos.append(vector)
      else:
        neg.append(vector)
        
    pos = np.concatenate(pos)
    neg = np.concatenate(neg)
    neg = np.random.permutation(neg)
    numpos = pos.shape[0]
    numneg = neg.shape[0]
    
    if local:
      filename = config.get_classifier_svm_name(self,cls)
    else:
      filename = config.get_classifier_svm_learning_filename(
        self,cls,kernel,intervals,lower,upper,C)
    model = load_svm(filename)
    evaluation = self.evaluate(pos, neg, model)
    pos_res = evaluation[:pos.shape[0],:]
    neg_res = evaluation[pos.shape[0]:,:]
    tp   = sum(pos_res > 0)
    fn   = sum(pos_res < 0)
    fp   = sum(neg_res < 0)
    tn   = sum(neg_res > 0)
    prec = tp/float(tp+fp)
    rec  = tp/float(tp+fn)
    eval_file = config.get_classifier_svm_learning_eval_filename(
      self,cls,kernel,intervals,lower,upper,C)
    acc = (tp/float(numpos)*numneg + tn)/float(2*neg.shape[0])
    if file_out:
      with open(eval_file, 'a') as myfile:
        myfile.write(cls + ' ' + str(np.array(prec)[0][0]) + ' ' + str(np.array(rec)[0][0]) + \
                     ' ' + str(np.array(acc)[0][0]) + '\n')
    else:
      return np.array(acc)[0][0]
    
  def get_best_svm_choices(self):  
    classes = config.pascal_classes
    maximas = {}
    for i in range(len(classes)):
      maximas[i] = 0  
    best_settings = {}
    kernels = config.kernels
    
    direct = get_classifier_svm_learning_dirname(self)
    for root, dirs, files in os.walk(direct):
      _,kernel =  os.path.split(root)    
      for direc in dirs:
        for filename in os.listdir(os.path.join(root,direc)):
          file_abs = os.path.join(root,direc,filename)
          if fnmatch.fnmatch(str(filename), 'eval_*'):
            infile = open(file_abs, 'r')
            for line in infile:
              words = line.split() 
              cls = words[0]
              cls_idx = classes.index(cls)
              if words[3] > maximas[cls_idx]:
                maximas[cls_idx] = words[3]
                file_spl = filename.split('_')
                lower = file_spl[1]
                upper = file_spl[2]
                C = file_spl[3]
                best_settings[cls] = [kernels.index(kernel),direc,lower,upper,C,words[3]]
            infile.close()  
    best_arr = np.zeros((20,7))
    cols = ['kernel', 'bins', 'lower', 'upper', 'C', 'score', 'cls_ind']
    for idx in range(len(classes)):
      best_arr[idx,:] = best_settings[classes[idx]] + [idx]
    
    # Store the best svms in results
    svm_save_dir = config.get_classifier_svm_dirname(self)
    score_sum = 0
    score_file = open(opjoin(svm_save_dir,'accuracy.txt'),'w')
    for row in best_arr:
      cls = classes[int(row[6])]
      svm_name = cls + '_' + str(row[2]) + '_' + \
        str(row[3]) + '_' + str(row[4])
      os.system('cp ' + config.data_dir + self.name+ '_svm_'+self.suffix+'/' + str(kernels[int(row[0])]) +\
                '/' + str(int(row[1])) + '/' + svm_name + ' ' + svm_save_dir + cls)
      score = row[5]
      score_sum += score
      score_file.writelines(cls + '\t\t\t' + str(score) + '\n')
      print svm_name
    score_file.writelines('mean' + '\t\t\t' + str(score_sum/20.) + '\n')
    
    best_table = ut.Table(best_arr, cols)
    best_table.name = 'Best_'+self.name+'_values'
    best_table.save(opjoin(svm_save_dir,'best_table'))
    print best_table
    
  def get_best_table(self):
    svm_save_dir = config.get_classifier_learning_dirname(self)
    return ut.Table.load(opjoin(svm_save_dir,'best_table'))
    
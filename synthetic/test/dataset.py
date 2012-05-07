from synthetic.common_imports import *

from synthetic.dataset import Dataset

class TestDatasetJson:
  def setup(self):
    self.d = Dataset('test_data1',force=True)
    self.classes = ["A","B","C"]

  def test_load(self):
    assert(self.d.num_images() == 4)
    assert(self.d.classes == self.classes)

  def test_get_det_gt(self):
    gt = self.d.get_det_gt(with_diff=True,with_trun=False)
    df = Table(
      np.array([[ 0.,  0.,  0.,  0.,  0.,  0, 0, 0.],
       [ 1.,  1.,  1.,  1.,  1.,  0, 0, 0.],
       [ 2.,  2.,  2.,  2.,  2.,  0, 0, 0.],
       [ 1.,  1.,  1.,  0.,  0.,  0, 0, 1.],
       [ 0.,  0.,  0.,  0.,  1.,  0, 0, 2.],
       [ 0.,  0.,  0.,  0.,  2.,  0, 0, 3.],
       [ 1.,  1.,  1.,  1.,  2.,  0, 0, 3.]]),
       ['x','y','w','h','cls_ind','diff','trun','img_ind'])
    print(gt)
    print(df)
    assert(gt == df)

  def test_get_cls_counts_json(self):
    arr = np.array(
      [ [ 1, 1, 1],
        [ 1, 0, 0],
        [ 0, 1, 0],
        [ 0, 0, 2]])
    print(self.d.get_cls_counts())
    assert(np.all(self.d.get_cls_counts() == arr))

  def test_get_cls_ground_truth_json(self):
    df = Table(
      np.array([ [ True, True, True],
        [ True, False, False],
        [ False, True, False],
        [ False, False, True] ]), ["A","B","C"])
    print(df)
    print(self.d.get_cls_ground_truth())
    assert(self.d.get_cls_ground_truth()==df)

  def test_det_ground_truth_for_class_json(self):
    gt = self.d.get_det_gt_for_class("A",with_diff=True,with_trun=True)
    arr = np.array(
      [[ 0.,  0.,  0.,  0.,  0., 0., 0, 0.],
       [ 1.,  1.,  1.,  0.,  0., 0., 0., 1.]])
    cols = ['x','y','w','h','cls_ind','diff','trun','img_ind']
    print(gt.arr)
    assert(np.all(gt.arr == arr))
    assert(gt.cols == cols)

    # no diff or trun
    gt = self.d.get_det_gt_for_class("A",with_diff=False,with_trun=False)
    arr = np.array(
      [[ 0.,  0.,  0.,  0.,  0., 0., 0, 0.],
       [ 1.,  1.,  1.,  0.,  0., 0., 0., 1.]])
    cols = ['x','y','w','h','cls_ind','diff','trun','img_ind']
    print(gt.arr)
    assert(np.all(gt.arr == arr))
    assert(gt.cols == cols)

class TestDatasetPascal:
  def setup(self):
    self.d = Dataset('test_pascal_train',force=True)
    
  def test_ground_truth_pascal_train(self):
    assert(self.d.num_classes() == 20)
    assert('dog' in self.d.classes)

  def test_ground_truth_for_class_pascal(self):
    correct = np.array(
      [[  48.,  240.,  148.,  132.,    11.,    1., 0.]])
    ans = self.d.get_det_gt_for_class("dog").arr
    print ans
    assert np.all(ans == correct)
      
  def test_neg_samples(self):
    # unlimited negative examples
    indices = self.d.get_neg_samples_for_class("dog",include_diff=True,include_trun=True)
    correct = np.array([1,2])
    assert(np.all(indices == correct))

    # maximum 1 negative example
    indices = self.d.get_neg_samples_for_class("dog",1,include_diff=True,include_trun=True)
    correct1 = np.array([1])
    correct2 = np.array([2])
    print(indices)
    assert(np.all(indices == correct1) or np.all(indices == correct2))

  def test_pos_samples(self):
    indices = self.d.get_pos_samples_for_class("dog")
    correct = np.array([0])
    assert(np.all(indices == correct))
    
  def test_ground_truth_test(self):
    d = Dataset('test_pascal_val')
    gt = d.get_ground_truth(include_trun=False).arr
    correct = np.matrix(
        [ [ 139.,  200.,   69.,  102.,   18.,   0.],
          [ 123.,  155.,   93.,   41.,   17.,   1.],
          [ 239.,  156.,   69.,   50.,    8.,   1.]])
    print(gt)
    assert np.all(gt == correct)

  def test_get_pos_windows(self):
    d = Dataset('test_pascal_val')
    
  def test_kfold(self):
    """
    'sizes' here are empirical values over the trainval set.
    """
    d = Dataset('full_pascal_trainval')
    numfolds = 4
    d.create_folds(numfolds)
    cls = 'dog'
    sizes = [314, 308, 321, 320]
    for i in range(len(d.folds)):
      d.next_folds()
      pos = d.get_pos_samples_for_fold_class(cls)
      neg = d.get_neg_samples_for_fold_class(cls, pos.shape[0])
      assert(pos.shape[0] == sizes[i])
      assert(neg.shape[0] == sizes[i])

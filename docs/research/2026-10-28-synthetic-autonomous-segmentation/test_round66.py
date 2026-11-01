import numpy as np
import round66

def test_score_reports_outside_and_small_core():
    core=np.array([[1,1,1,0]],bool);pred=np.array([[1,0,1,1]],bool);truth=np.array([[1,1,0,0]],bool);big=np.array([[1,0,0,0]],bool);small=np.array([[0,1,0,0]],bool)
    m=round66.score(pred,core,truth,big,small)
    assert m['dice']==.5 and m['relative_area_error']==0 and m['small_recall']==0 and m['outside_pred_pixels']==1

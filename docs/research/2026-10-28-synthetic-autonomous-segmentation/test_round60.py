import importlib.util
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent));s=importlib.util.spec_from_file_location('r60',Path(__file__).with_name('round60.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_prompt_limits_and_unprocessed_become_unknown():
    strong=np.zeros((20,20),bool);strong[2:5,2:5]=True;strong[15,15]=True;unknown=np.zeros_like(strong)
    labels,p,dropped=r.prompts(strong,limit=1);assert len(p)==1 and dropped==1 and strong[p[0]['point'][1],p[0]['point'][0]]
    new,u=r.refine_from_masks(strong,unknown,labels,p,[np.ones_like(strong)])
    assert new[2:5,2:5].all() and not new[15,15] and u[15,15] and np.array_equal(new|u,strong)

def test_no_candidates_do_not_call_or_create_lesions():
    strong=np.zeros((8,8),bool);labels,p,d=r.prompts(strong);new,u=r.refine_from_masks(strong,strong,labels,p,[])
    assert not p and d==0 and not new.any() and not u.any()

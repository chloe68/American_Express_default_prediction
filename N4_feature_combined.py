import warnings
warnings.simplefilter('ignore')

import pandas as pd
from tqdm import tqdm

from utils import *

root = args.root

oof = pd.read_csv('./output/LGB_with_series_feature/oof.csv')
sub = pd.read_csv('./output/LGB_with_series_feature/submission.csv.zip')

def pad_target(x):
    t = np.zeros(13)
    t[:-len(x)] = np.nan
    t[-len(x):] = x
    return list(t)

tmp1 = oof.groupby('customer_ID',sort=False)['target'].agg(lambda x:pad_target(x))
tmp2 = sub.groupby('customer_ID',sort=False)['prediction'].agg(lambda x:pad_target(x))

tmp = tmp1.append(tmp2)

tmp = pd.DataFrame(data=tmp.tolist(),columns=['target%s'%i for i in range(1,14)])


df = []
for fn in ['cat','num','diff','rank_num','last3_cat','last3_num','last3_diff', 'last6_num','ym_rank_num']:
    if len(df) == 0:
        df.append(pd.read_feather(f'{root}/{fn}_feature.feather'))
    else:
        df.append(pd.read_feather(f'{root}/{fn}_feature.feather').drop([id_name],axis=1))
    if 'last' in fn :
        df[-1] = df[-1].add_prefix('_'.join(fn.split('_')[:-1])+'_')

df.append(tmp)

df = pd.concat(df,axis=1)
print(df.shape)
df.to_feather(f'{root}/all_feature.feather')

del df

def one_hot_encoding(df,cols,is_drop=True):
    for col in cols:
        print('one hot encoding:',col)
        dummies = pd.get_dummies(pd.Series(df[col]),prefix='oneHot_%s'%col)
        df = pd.concat([df,dummies],axis=1)
    if is_drop:
        df.drop(cols,axis=1,inplace=True)
    return df

cat_features = ["B_30","B_38","D_114","D_116","D_117","D_120","D_126","D_63","D_64","D_66","D_68"]

df = pd.read_feather(f'./input/train.feather').append(pd.read_feather(f'./input/test.feather')).reset_index(drop=True)
df = df.drop(['S_2'],axis=1)
df = one_hot_encoding(df,cat_features,True)
for col in tqdm(df.columns):
    if col not in ['customer_ID','S_2']:
        df[col] /= 100
    df[col] = df[col].fillna(0)

df.to_feather('./input/nn_series.feather')

def GreedyFindBin(distinct_values, counts,num_distinct_values, max_bin, total_cnt, min_data_in_bin=3):
#INPUT:
#   distinct_values
#   counts
#   num_distinct_values
#   max_bin 
#   total_cnt 
#   min_data_in_bin 

# bin_upper_bound
    bin_upper_bound=list();
    assert(max_bin>0)

    if num_distinct_values <= max_bin:
        cur_cnt_inbin = 0
        for i in range(num_distinct_values-1):
            cur_cnt_inbin += counts[i]
           
            if cur_cnt_inbin >= min_data_in_bin:
                
                bin_upper_bound.append((distinct_values[i] + distinct_values[i + 1]) / 2.0)
                cur_cnt_inbin = 0
        
        cur_cnt_inbin += counts[num_distinct_values - 1];
        bin_upper_bound.append(float('Inf'))
        
    else:
        if min_data_in_bin>0:
            max_bin=min(max_bin,total_cnt//min_data_in_bin)
            max_bin=max(max_bin,1)
        #mean size for one bin
        mean_bin_size=total_cnt/max_bin
        rest_bin_cnt = max_bin
        rest_sample_cnt = total_cnt
       
        is_big_count_value=[False]*num_distinct_values
       
        for i in range(num_distinct_values):
        
            if counts[i] >= mean_bin_size:
                is_big_count_value[i] = True
                rest_bin_cnt-=1
                rest_sample_cnt -= counts[i]
       
        mean_bin_size = rest_sample_cnt/rest_bin_cnt
        upper_bounds=[float('Inf')]*max_bin
        lower_bounds=[float('Inf')]*max_bin

        bin_cnt = 0
        lower_bounds[bin_cnt] = distinct_values[0]
        cur_cnt_inbin = 0
       
        for i in range(num_distinct_values-1):
            #如果当前的特征值数目是小的
            if not is_big_count_value[i]:
                rest_sample_cnt -= counts[i]
            cur_cnt_inbin += counts[i]

          
            if is_big_count_value[i] or cur_cnt_inbin >= mean_bin_size or \
            is_big_count_value[i + 1] and cur_cnt_inbin >= max(1.0, mean_bin_size * 0.5):
                upper_bounds[bin_cnt] = distinct_values[i]
                bin_cnt+=1
                lower_bounds[bin_cnt] = distinct_values[i + 1] 
                if bin_cnt >= max_bin - 1:
                    break
                cur_cnt_inbin = 0
                if not is_big_count_value[i]:
                    rest_bin_cnt-=1
                    mean_bin_size = rest_sample_cnt / rest_bin_cnt
#             bin_cnt+=1
       
        for i in range(bin_cnt-1):
            bin_upper_bound.append((upper_bounds[i] + lower_bounds[i + 1]) / 2.0)
        bin_upper_bound.append(float('Inf'))
    return bin_upper_bound

cat_features = ["B_30","B_38","D_114","D_116","D_117","D_120","D_126","D_63","D_64","D_66","D_68"]
eps = 1e-3

dfs = []
for fn in ['cat','num','diff','rank_num','last3_cat','last3_num','last3_diff', 'last6_num','ym_rank_num']:
    if len(dfs) == 0:
        dfs.append(pd.read_feather(f'{root}/{fn}_feature.feather'))
    else:
        dfs.append(pd.read_feather(f'{root}/{fn}_feature.feather').drop(['customer_ID'],axis=1))

    if 'last' in fn:
        dfs[-1] = dfs[-1].add_prefix('_'.join(fn.split('_')[:-1])+'_')

for df in dfs:
    for col in tqdm(df.columns):
        if col not in ['customer_ID','S_2']:
            # v_min = df[col].min()
            # v_max = df[col].max()
            # df[col] = (df[col]-v_min+eps) / (v_max-v_min+eps)
            vc = df[col].value_counts().sort_index()
            bins = GreedyFindBin(vc.index.values,vc.values,len(vc),255,vc.sum())
            df[col] = np.digitize(df[col],[-np.inf]+bins)
            df.loc[df[col]==len(bins)+1,col] = 0
            df[col] = df[col] / df[col].max()

tmp = tmp.fillna(0)
dfs.append(tmp)
df = pd.concat(dfs,axis=1)

df.to_feather('./input/nn_all_feature.feather')

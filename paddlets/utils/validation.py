#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from typing import List, Callable, Optional, Union

import numpy as np

from paddlets.datasets.tsdataset import TSDataset
from paddlets.metrics.base import Metric
from paddlets.metrics.metrics import MAE
from paddlets.models.base import Trainable
from paddlets.datasets.splitter import SplitterBase, ExpandingWindowSplitter
from paddlets.logger import Logger, raise_if_not
from paddlets.utils.backtest import backtest
from paddlets.utils import check_train_valid_continuity

logger = Logger(__name__)

def cross_validate(
        data: TSDataset,
        estimator: Trainable,
        splitter: SplitterBase = ExpandingWindowSplitter(),
        use_backtest:bool = True,
        predict_window: int = None,
        stride: int = None,
        metric: Optional[Metric] = None,
        return_score = True,
        reduction: Union[Callable[[np.ndarray], float], None] = np.mean,
        verbose: bool = False,
) -> Union[float, List[dict]]:
    """
    Cross validate
    Evaluate forecaster using timeseries cross-validation.

    Args:
        data(TSDataset): The  TSdataset to use in cross validate.
        estimator(Trainable): The  model use in cross validate.
        splitter(SplitterBase): CV splitter, use 5-folds ExpandingWindowSplitter by default.
        use_backtest(bool):Use backtest or not, set to True by default, use recursive predict if False.
        predict_window(int): The size of  predict window for the  prediction.
        stride(int): The number of time steps between two consecutive predict window.
        metric(Metric): A function that takes two ``TSdataset`` instances as inputs and returns an error value.
        return_score(bool): Compute and return score on test set. Will return a list of dict if set to False
        reduction(Callable[[np.ndarray]|None):A function used to combine the individual error scores obtained when predict_window ！= stride.
            If explicitely set to `None`, the method will return a list of the individual error scores instead.
            Set to ``np.mean`` by default.
        verbose(bool): Verbose mode.

    Return:
        float, list[dict]

    Raise:
        ValueError

    """
    raise_if_not(isinstance(estimator, Trainable), "Estimator not right, check instructions to get valid estimators.")
    raise_if_not(isinstance(splitter, SplitterBase), "Splitter not right, check instructions to get valid splitters.")
    splits = splitter.split(data)

    if metric is None:
        metric = MAE()
    res = [fit_and_score(train_data,
                             test_data,
                             estimator,
                             use_backtest,
                             predict_window,
                             stride,
                             metric,
                             True,
                             True,
                             True,
                             reduction,
                             verbose
                             )
              for train_data, test_data in splits]
    if return_score:
        
        return np.mean([dict["score"] for dict in res])
    else:
        return res


def fit_and_score(
        train_data: TSDataset,
        valid_data: TSDataset,
        estimator: Trainable,
        use_backtest:bool = True,
        predict_window: int = None,
        stride: int = None,
        metric: Optional[Metric] = None,
        return_score = True,
        return_estimator = True,
        return_predicts = True,
        reduction: Union[Callable[[np.ndarray], float], None] = np.mean,
        verbose: bool = False
) -> dict:
    """
    Fit and score
    
    Args:
        train_data(TSDataset): Train dataset .
        test_data(TSDataset): Test dataset .
        estimator(Trainable): The  model use in cross validate.
        use_backtest(bool):Use backtest or not.
        predict_window(int): The predict window for the  prediction.
        stride(int): The number of time steps between two consecutive predict window.
        metric(Metric): A function that takes two ``TSdataset`` instances as inputs and returns an error value.
        verbose(bool): verbose mode.
        return_score(bool): Compute and return score on test set.
        return_estimator(bool): Whether to return the fitted estimator.
        reduction(Callable[[np.ndarray]|None):A function used to combine the individual error scores obtained when predict_window ！= stride.
            If explicitely set to `None`, the method will return a list of the individual error scores instead.
            Set to ``np.mean`` by default.

    Return:
        dict

    Raise:
        ValueError
    
    """
    estimator.fit(train_data, valid_data)

    start = None
    if check_train_valid_continuity(train_data, valid_data):
        data = TSDataset.concat([train_data, valid_data], drop_duplicates=True)
        start = len(train_data.get_target())
    else:
        data = valid_data
        if verbose:
            logger.info("Train and valid are not continious, the initial in_chunk_len points of valid data will use as model input")

    if use_backtest: 
        score_dict, predicts = backtest(data,
                        estimator,
                        start,
                        predict_window,
                        stride,
                        metric,
                        True,
                        reduction,
                        verbose 
                        )
    else:
        predict_length = valid_data.get_target().__len__()
        predicts = estimator.recursive_predict(train_data, predict_length)
        score_dict = metric(valid_data, predicts)
    
    #quantile metric(get mean value temporary, need to be optimized.)
    if metric._TYPE == "quantile" and isinstance(list(score_dict[0].values())[0], dict):
        score = np.mean([list(x.values()) for x in score_dict.values()])
    else:
        #multi-targets(get mean value temporary, need to be optimized.)
        score = np.mean([x for x in score_dict.values()])

    res = {}
    if return_score:
        res["score"] = score
    if return_estimator:
        res["estimator"] = estimator
    if return_predicts:
        res["predicts"] = predicts
    return res


import ray
import numpy as np
from tqdm import tqdm
from itertools import product, islice
from utils import logger
from config import USGDict
from Models.utils import loadModel, saveModel
from Models.USG.lib.FriendBasedCF import FriendBasedCF, friend_based_cf_predict


modelName = 'USG'

CHUNK_SIZE = 64


def batched(iterable, n):
    "Batch data into tuples of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    while (batch := tuple(islice(iterable, n))):
        yield batch


def friendBasedCalculations(datasetName: str, users: dict, pois: dict, socialRelations, trainingMatrix, groundTruth):
    # Initializing parameters
    userCount = users['count']
    eta = USGDict['eta']
    SScores = np.zeros((users['count'], pois['count']))
    # Checking for existing model
    logger('Preparing Friend-based CF matrix ...')
    loadedModel = loadModel(modelName, datasetName, f'S_{userCount}User')
    if loadedModel == []:  # It should be created
        # Creating object to S Class
        S = FriendBasedCF(eta)
        # Calculating S scores
        # TODO: We may be able to load the model from disk
        S.friendsSimilarityCalculation(socialRelations, trainingMatrix)

        print(f"Users in GT: {len(groundTruth)}")
        print(f"POIs: {len(pois['list'])}")

        # for uid in tqdm(users['list']):
        #     if uid in groundTruth:
        #         for lid in pois['list']:
        #             SScores[uid, lid] = S.predict(uid, lid)

        # Try and use ray instead

        refs = S.loadObjectsIntoRay()
        inputs = (uid for uid in users['list'] if uid in groundTruth)
        for batch in tqdm(batched(inputs, CHUNK_SIZE)):
            results = ray.get([
                friend_based_cf_predict.remote(
                    uid, refs['eta'], refs['socialProximity'], refs['checkinMatrix'], pois['ref']
                )
                for uid in batch
            ])
            for uid, lid_scores in zip(batch, results):
                np.copyto(SScores[uid, :], lid_scores)

        saveModel(SScores, modelName, datasetName, f'S_{userCount}User')
    else:  # It should be loaded
        SScores = loadedModel
    # Returning the scores
    return SScores

import numpy as np
from utils import logger
from config import limitUsers, topK, listLimit
from Evaluations.evaluator import evaluator
from Data.readDataSizes import readDataSizes
from Models.GeoSoCa.social import socialCalculations
from Data.calculateActiveUsers import calculateActiveUsers
from Models.GeoSoCa.categorical import categoricalCalculations
from Models.GeoSoCa.geographical import geographicalCalculations
from Models.Reranking import rerankPredictions
from Models.utils import readPoiCoos, readTestData, readCategoryData, readTrainingData, readFriendData
from Models.scoring import calculateScores

modelName = 'GeoSoCa'


class GeoSoCaMain:
    def main(datasetFiles, params):
        logger(f'Processing data using {modelName} model ...')

        # Reading data size from the selected dataset
        dataDictionary = readDataSizes(params['datasetName'], datasetFiles)
        users, pois, categories = dataDictionary['users'], dataDictionary['pois'], dataDictionary['categories']

        # Skipped context
        skipCategory = bool(categories['count'] == 0)

        # Loading data from the selected dataset
        logger('Reading dataset instances ...')
        poiCoos = readPoiCoos(datasetFiles['poiCoos'])
        trainingMatrix, userCheckinCounts, poiCheckinCounts = readTrainingData(
            datasetFiles['train'], users['count'], pois['count'], True)
        socialRelations = readFriendData(
            datasetFiles['socialRelations'], 'ndarray', users['count'])
        groundTruth = readTestData(datasetFiles['test'])
        # If the dataset does not cover categories, do not read them
        poiCategoryMatrix = np.empty((0, 0))
        if not skipCategory:
            poiCategoryMatrix = readCategoryData(
                datasetFiles['poiCategories'], categories['count'], pois['count'])

        # Limit the number of users
        if (limitUsers != -1):
            logger(f'Limiting the number of users to {limitUsers} ...')
            users['count'] = limitUsers
            users['list'] = users['list'][:limitUsers]

        # Computing the final scores
        AKDEScores = geographicalCalculations(
            params['datasetName'], users, pois, poiCoos, trainingMatrix, groundTruth)
        SCScores = socialCalculations(
            params['datasetName'], users, pois, trainingMatrix, socialRelations, groundTruth)
        CCScores = None
        if not skipCategory:
            CCScores = categoricalCalculations(
                params['datasetName'], users, pois, trainingMatrix, poiCategoryMatrix, groundTruth)

        # Segmenting active users
        calculateActiveUsers(params['datasetName'], datasetFiles['train'])

        # Score calculation
        # (Moving this before evaluation so that we can test reranking methods)
        evalParams = {'usersList': users['list'], 'usersCount': users['count'],
                      'groundTruth': groundTruth, 'fusion': params['fusion'], 'poiList': pois['list'],
                      'trainingMatrix': trainingMatrix, 'evaluation': params['evaluation']}
        modelParams = {'AKDE': AKDEScores, 'SC': SCScores, 'CC': CCScores}
        predictions, scores = calculateScores(
            modelName, evalParams, modelParams, listLimit)

        # Reranking
        # Reranking
        predictions = rerankPredictions(
            params['reranker'],
            predictions,
            k=topK,
            userCheckinCounts=userCheckinCounts,
            poiCheckinCounts=poiCheckinCounts,
            scalingFactor=10,
            predictionScores=scores
        )

        # Evaluation
        evaluator(
            modelName, params['reranker'], params['datasetName'], evalParams,
            modelParams, predictions, userCheckinCounts=userCheckinCounts,
            poiCheckinCounts=poiCheckinCounts
        )

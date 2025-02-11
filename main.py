from data_generator_VFL import dataGeneratorVFL
from dataGenerator import dataGeneratorHFL
from VFL import *
from VFL_Ray import *
from federatedAlgs import federatedFunctionalGradBoostLSA, federatedFunctionalGradBoostAvg

def simulationStudyVFL(numSamples=100, num_duplicate=2):
    dataGeneratorVFL(numSamples, num_duplicate)
    # number of basis functions in basis system
    t = 20
    rangeval = [0, 100]
    numworkersseq = [2]

    times = np.zeros([5, num_duplicate, 2])

    basisobj = create_bspline_basis(rangeval, t)
    betaPar = fdPar(basisobj, 0, 0)
    yfine = np.linspace(1, 100, 100)
    bbspl2 = bifd(np.linspace(1, pow(t, 2), pow(t, 2)).reshape((t, t)), create_bspline_basis(rangeval, t),
                  create_bspline_basis(rangeval, t))
    bifdbasis = bifdPar(bbspl2, 0, 0, 0, 0)
    betaList = [betaPar, bifdbasis]
    cv = 5
    k = numworkersseq[0]
    for hh in range(num_duplicate):
        for num_cv in range(cv):
            print(f'VFL: Duplicate {hh}; {num_cv} fold.')
            samples = np.linspace(0, numSamples - 1, numSamples)
            test = samples[int((num_cv - 1) * (numSamples / cv)): int(num_cv * numSamples / cv)]
            test = test.astype(int)
            train = np.setdiff1d(samples, test)
            train = train.astype(int)

            step_length = 0.1
            epsilon = 5
            delta = 0.05
            boost_control = 5
            trainPredictorLst = []
            testPredictorLst = []
            for l in range(2):
                with open('tmp/predictorLst_' + str(l) + '_' + str(k) + '_' + str(hh), 'rb') as file:
                    predictorLst = pickle.load(file)
                    for num in range(len(predictorLst)):
                        temp1 = copy.copy(predictorLst[num])
                        temp2 = copy.copy(predictorLst[num])
                        temp1.coef = temp1.coef[:, train]
                        temp2.coef = temp2.coef[:, test]
                        trainPredictorLst.append(temp1)
                        testPredictorLst.append(temp2)

            with open('tmp/yfdobj_' + str(k) + '_' + str(hh), 'rb') as file:
                yfdobj = pickle.load(file)
            temp1 = copy.copy(yfdobj)
            temp2 = copy.copy(yfdobj)
            temp1.coef = temp1.coef[:, train]
            temp2.coef = temp2.coef[:, test]
            x = trainPredictorLst
            y = [temp1]
            curTime = time.time()
            res = verticalFederatedFunctionalGradBoost(x, y, betaList, boost_control, step_length, epsilon, delta)
            times[num_cv, hh, 0] = time.time() - curTime
            curTime = time.time()
            res = verticalFederatedFunctionalGradBoostRay(x, y, betaList, boost_control, step_length, epsilon, delta)
            times[num_cv, hh, 1] = time.time() - curTime
    print("Comparison of operation times of VFL with Ray and without Ray")
    print('operation times without Ray')
    print(np.mean(times[:, :, 0]))
    print('operation times of with Ray')
    print(np.mean(times[:, :, 1]))
    return times

def simulationStudyHFL():
    dataGeneratorHFL()
    # number of basis functions in basis system
    t = 20
    rangeval = [0, 100]
    basisobj = create_bspline_basis(rangeval, t)
    # number of observations pre local server n
    n = 100
    # number of features p 20
    p = 20
    betaPar = fdPar(basisobj, 0, 0)
    # number of observations pre local server n
    samplesPerWorker = 100
    # number of features p 20
    numPredictors = 20
    yfine = np.linspace(1, 100, 100)
    allsamples = set([i for i in range(100)])
    numworkersseq = [4]
    bbspl2 = bifd(np.linspace(1, pow(t, 2), pow(t, 2)).reshape((t, t)), create_bspline_basis(rangeval, t),
                  create_bspline_basis(rangeval, t))
    bifdbasis = bifdPar(bbspl2, 0, 0, 0, 0)
    betaList = [betaPar, bifdbasis]
    time1 = np.zeros([len(numworkersseq), 4])
    time2 = np.zeros([len(numworkersseq), 4])

    for numworkers in numworkersseq:
        # 4-fold CV
        for hh in range(4):
            print(f'HFL: Number of local servers : {numworkers}; {hh} fold.')
            test = set([i for i in range(hh * 25, (hh + 1) * 25)])
            train = list(allsamples - test)
            predictors = np.zeros([len(yfine), samplesPerWorker * numworkers, numPredictors])
            response = np.zeros([len(yfine), samplesPerWorker * numworkers])
            x = []
            y = []
            for l in range(1, numworkers + 1):
                with open('tmp/yfdobj_' + str(l) + '_' + str(numworkers), 'rb') as file:
                    yfdobj = pickle.load(file)
                with open('tmp/predictorLst_' + str(l) + '_' + str(numworkers), 'rb') as file:
                    predictorLst = pickle.load(file)
                xfdobjTrainLst = []
                for i in range(numPredictors):
                    predictors[:, (samplesPerWorker * (l - 1)): (samplesPerWorker * l), i] = eval_fd(yfine,
                                                                                                     predictorLst[i])
                    temp1 = smooth_basis(yfine, predictors[:, [i + samplesPerWorker * (l - 1) - 1 for i in train], i],
                                         basisobj).fd
                    xfdobjTrainLst.append(temp1)
                x.append(xfdobjTrainLst)
                response[:, (samplesPerWorker * (l - 1)): (samplesPerWorker * l)] = eval_fd(yfine, yfdobj)
                responsefdobjTrain = smooth_basis(yfine,
                                                  response[:, [i + samplesPerWorker * (l - 1) - 1 for i in train]],
                                                  basisobj).fd
                y.append(responsefdobjTrain)

            boost_control = 10
            step_length = 0.5
            start = time.time()
            federatedFunctionalGradBoostLSA(x, y, betaList, boost_control, step_length, ray_control = True)
            end = time.time()
            time1[numworkersseq.index(numworkers), hh] = end - start
            start = time.time()
            federatedFunctionalGradBoostLSA(x, y, betaList, boost_control, step_length, ray_control = False)
            end = time.time()
            time2[numworkersseq.index(numworkers), hh] = end - start
    print("Comparison of operation times of fed-GB-LSA (LSA) with and without Ray")
    print('operation times of fed-GB-LSA (LSA) with Ray')
    print(np.mean(time1, 1))
    print('operation times of fed-GB-LSA (LSA) without Ray')
    print(np.mean(time2, 1))
    return 0


if __name__ == '__main__':
    model = input("Please tell me which federated learning frameworks you are looking for? HFL/VFL : ")
    while True:
        if model == 'HFL':
            simulationStudyHFL()
            break
        elif model == 'VFL':
            numSamples = 100
            num_duplicate = 5
            times = simulationStudyVFL(numSamples, num_duplicate)
            print(f'The average time saving by Ray is {np.mean(times[:, :, 0] - times[:, :, 1])} seconds per training.')
            break
        elif model == 'quit':
            break
        else:
            print(f'Your input "{model}" is illegal, please pick from HFL/VFL. If you want to quit this program, please input "quit".')
            model = input("Please tell me which federated learning frameworks you are looking for? HFL/VFL : ")


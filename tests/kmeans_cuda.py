import argparse
import libKMCUDA
import numpy
import pandas
import csv
import objsize

# def euclid_dist_2(coord1, coord2):
#     """
#     Calculate the euclidean distance between two points
#
#     Inputs:
#         coord1: the attributes contained by point 1
#         coord2: the attributes contained by point 2
#
#     Output:
#         The euclidean distance without taking square root.
#     """
#     return sum([(a - b) ** 2 for a, b in zip(coord1, coord2)])
#
#
# def find_nearest_cluster(obj, clusters):
#     """
#     Find out the nearest cluster for a point
#
#     Input:
#         obj: the point to be assigned to the nearest cluster
#         clusters: the list contains attributes of all clusters
#
#     Output:
#         the index of the nearest cluster to the point
#     """
#     index = 0
#     min_dist = euclid_dist_2(obj, clusters[0])
#     for i in range(1, len(clusters)):
#         dist = euclid_dist_2(obj, clusters[i])
#         if dist < min_dist:
#             min_dist = dist
#             index = i
#
#     return index
#
#
# def kmeans(objects, numClusters, threshold):
#     """
#     runs the k-means algorithm.
#
#     Input:
#         objects: [numObjs][numCoords]
#         numClusters: # clusters
#         threshold: objects change membership
#     Output:
#         a tuple contains:
#             clusters: [numClusters][numCoords]
#             membership: [numObjects]
#     """
#     clusters = []
#     newClusters = [x[:] for x in [[0.0] * len(objects[0])] * numClusters]
#     newClusterSize = [0 for i in range(numClusters)]
#     membership = [-1 for i in range(len(objects))]
#     loop = 0
#
#     # pick first numCluster elements of objects as initial cluster centers
#     for i in range(numClusters):
#         clusters.append(objects[i])
#
#     # emulate do-while loop
#     while True:
#         delta = 0.0
#         for i, obj in enumerate(objects):
#             index = find_nearest_cluster(obj, clusters)
#
#             # /* if membership changes, increase delta by 1 * /
#             # /* assign the membership to object i * /
#             if membership[i] != index:
#                 delta += 1.0
#                 membership[i] = index
#
#             newClusterSize[index] += 1
#
#             # /* update new cluster centers: sum of objects located within * /
#             for j, attr in enumerate(obj):
#                 newClusters[index][j] += attr
#
#         # /* average the sum and replace old cluster centers with newClusters * /
#         for i in range(numClusters):
#             for j in range(len(obj)):
#                 if (newClusterSize[i] > 0):
#                     clusters[i][j] = newClusters[i][j] / newClusterSize[i]
#                 newClusters[i][j] = 0.0
#             newClusterSize[i] = 0
#
#         delta /= len(objects)
#
#         if not (delta > threshold and loop < 500):
#             break
#         loop += 1
#
#     return (clusters, membership)
#

# def file_read(filename):
#     """
#     Read the file to parse to a matrix
#
#     Input:
#         filename: the input filename
#
#     Output:
#         objects: a matrix contains attributes of objects in the file.
#     """
#     f = open(filename, 'r')
#     a = np.asarray(list(csv.reader(f, delimiter=' ')), 'float32')
#     f.close()
#     return a
#
#
# def file_write(filename, clusters, membership):
#     """
#     Write the attributes of clusters and the cluster index of each object
#     to the file
#
#     Input:
#         filename: input file name
#         clusters: attribute matrix of clusters
#         membership: list of cluster index for all objects.
#     """
#     with open('{}.cluster_centres'.format(filename), 'w') as f:
#         for i, cluster in enumerate(clusters):
#             # f.write('{}'.format(i))
#             for attr in cluster:
#                 f.write(' {:.6f}'.format(attr))
#             f.write('\n')
#
#     with open('{}.membership'.format(filename), 'w') as f:
#         for i, member in enumerate(membership):
#             f.write('{} {}\n'.format(i, member))



parser = argparse.ArgumentParser()
parser.add_argument('filename', help='input filename')
parser.add_argument('-k', type=int, dest="numClusters", default=5, help='number of clusters')
parser.add_argument('-t', type=float, dest="threshold", default=0.001, help='number of clusters')
parser.add_argument('--time', dest="is_output_timing", action='store_true', help='output the timing')
args = parser.parse_args()

filename = args.filename
f = open(filename, 'r')
a = numpy.genfromtxt(f)
a
# clusters, membership = libKMCUDA.kmeans_cuda(a, args.numClusters, seed=5)

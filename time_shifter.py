#functions / classes to generate timing shifts in patterns

from random import choice
import numpy as np


def lex_partitions(n):
    """IntegerPartitions.py

    Generate and manipulate partitions of integers into sums of integers.

    D. Eppstein, August 2005.
    """


    """Similar to revlex_partitions, but in lexicographic order."""
    if n == 0:
        yield []
    if n <= 0:
        return
    for p in lex_partitions(n-1):
        p.append(1)
        yield p
        p.pop()
        if len(p) == 1 or (len(p) > 1 and p[-1] < p[-2]):
            p[-1] += 1
            yield p
            p[-1] -= 1



class partition_shifter():
    #for an n-spot target pattern, generate a vector of timing shifts for each spot
    #probabilistically but uniformly across a range of total absolute shift

    parts_sampling = {}
    parts_sampling[1] = {2:0,
                   4:0.3,
                   6:0.3,
                   8:0.3,
                   10:0.05,
                   12:0,
                   14:0,
                   16:0.05}
    
    parts_sampling[2] = {2:0,
                   4:0,
                   6:0,
                   8:0,
                   10:0.25,
                   12:0.25,
                   14:0.25,
                   16:0.25}    
    
    


    target_t = [10,50,90,130,170,210]
    old_target = [(10, 90), (50, 130),(90, 170), (130, 210), (170, 250), (210, 290)]


    def __init__(self, sample_number):
        self.parts={}
        self.tshifts=[]
        self.tweights=[]

        self.parts_ratio=self.parts_sampling[sample_number]
        self.gen_partition_doublets()



    def gen_partition_doublets(self):
        #Resolution 20ms. Oversampling of some small shifts,
        #and limited sampling of some large shifts
        parts={}

        nSpots=6
        maxSingleShift = 4

        for shift in range(2,9):
            parts[shift*2]=[]
            for x in lex_partitions(shift):

                if (x[0]*2) > maxSingleShift:
                    break #don't accept single spot shift > maxSingleShift
                if 1 < len(x) <= nSpots:
                    y = x + [0] * (nSpots - len(x)) #zero pad
                    y = list(np.array(y)*2) #multiply by 2
                    parts[shift*2].append(y)

        parts[2]=[[1,1,0,0,0,0]]

        tweights=[]
        tshifts=[]

        for t in parts:
            if self.parts_ratio[t] == 0:
                continue
            tweights.append(self.parts_ratio[t])
            tshifts.append(t)

        self.tweights = tweights
        self.tshifts = tshifts
        self.parts = parts

    def select_t(self):
        return np.random.choice(self.tshifts,1,p=self.tweights)[0]

    def select_part(self):
        shift=self.select_t()
        flag = 1

        while flag:
            #keep looping until allowable partition is found.
            #all spots should end up with non-negative timing.

            if len(self.parts[shift])==1:
                shift_vec = self.parts[shift][0]
            else:
                shift_vec=choice(self.parts[shift])


            shift_vec = np.random.permutation([choice([-10,10]) *s for s in shift_vec])
            probe_t=[]
            for t1,t2 in zip(self.target_t,shift_vec):
                probe_t.append(t1+t2)

            if sum(np.array(probe_t)<0) > 0:
                probe_t = [max(0,p) for p in probe_t]
                flag = 1
            else:
                flag = 0

        return shift_vec

    def get_shift_map(self):
        shift_vec=self.select_part()

        shift_map={}
        print shift_vec
        for t_old,shift_new in zip(self.old_target,shift_vec):
            t_new = list(np.array(t_old)+shift_new)
            shift_map[t_old]=t_new

        return shift_map
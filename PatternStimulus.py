#add leading underscore to indicate stimulus is odor
def underscore_odordict(odordict):
    for trialtype in odordict:
        for i,o in enumerate(odordict[trialtype]):
            if not '!' in o: #make sure that pattern/odor combinations are not declared as odors
                odordict[trialtype][i]='_'+o


class intensityStaircase():
    intensities = [255,200,128,110,100,90,80,70,60,50,40,30,20,10]
    currentStep = 0
    consec_correct = 0
    up=0
    down=1

    def __init__(self,up, down, intensities=[]):
        if len(intensities) > 0 :
            self.intensities = intensities

        if not self.strictly_decreasing(self.intensities):
            print 'intensities: ' + str(self.intensities)
            raise ValueError('Intensities should be in a monotonic decreasing list')



        self.up = up
        self.down = down

    def update(self, correct):
        if correct:
            self.consec_correct +=1

            if self.consec_correct == self.up:
                self.consec_correct = 0
                self.currentStep = min(self.currentStep + 1, len(self.intensities) - 1)
        else:
            self.consec_correct = 0
            self.currentStep = max(0,self.currentStep - 1)




    def get_intensity(self):
        return self.intensities[self.currentStep]

    def strictly_decreasing(self,L):
        #check that list is strictly decreasing
        return all(x>y for x, y in zip(L, L[1:]))







class Odor():

    def __init__(self,textstr):
        odorparams=textstr.split('_')

        self.name=odorparams[0]
        self.liq_dilution=float(odorparams[1])

        nitrogen=int(odorparams[2])
        self.flow=[1000-nitrogen, nitrogen]

class OdorMixture():
    #format of string:
    # OdorA;OdorB_liqdilution1;liqdilution2_nitrogen1;nitrogen2

    def __init__(self,textstr):
        odorparams=textstr.split('_')

        self.name= [ str(oname) for oname in odorparams[0].split(';') ]
        self.liq_dilution = [ float(oparam) for oparam in odorparams[1].split(';') ]
        self.flow = [ [500-int(nitrogen), int(nitrogen)] for nitrogen in odorparams[2].split(';') ]

def get_pattern_params(spotlist,ptn,sessNow):
    xy=[]
    timing=[]
    intensities=[]
    grouptimes=[]

    rand_args = {} #initialize dictionary of global sequence parameters
    for p in ['omit','replace','scramble','randt','randdur','randxyt','meanT']:
        rand_args[p]=0

    if 'empty' in ptn:
        xy=[[0,0]]
        timing=[[0,1]]
        intensities=[0]
        grouptimes=[]
        return xy,timing,intensities,grouptimes,rand_args


    if not 'defn' in sessNow['patterns'][ptn]:
        sessNow['patterns'][ptn]['defn'] = sessNow['patterns'][ptn].copy()
    patterndict = sessNow['patterns'][ptn]['defn']


    for spotLetter in patterndict:
        onset = patterndict[spotLetter]['onset']
        dur = patterndict[spotLetter]['dur']

        if 'intensity' in patterndict[spotLetter]: #backward compatibility
            intensity = patterndict[spotLetter]['intensity']
        else:
            intensity = 255

        if 'grouptime' in patterndict[spotLetter]: #backward compatibility
            grouptime = patterndict[spotLetter]['grouptime']
            grouptimes.append(grouptime)
        else:
            pass

        if isinstance(onset,list):
            timing.append([onset,dur])
        else:
            offset=onset+dur
            timing.append([onset,offset])

        if spotLetter.startswith('R'):
            xy.append(['random'])
        else:
            xy.append(spotlist[spotLetter])


        intensities.append(intensity)


    for p in rand_args:
        if p in sessNow['patterns'][ptn]:
            rand_args[p]=sessNow['patterns'][ptn][p]
    return xy, timing, intensities, grouptimes, rand_args




class OptoOdorStimulus():
    ''' stimulus for odor emulation experiments. in each trial, either odor or optogenetic pattern,
    and both the laser and FV are turned on across both trials just to be controlled'''

    description = '' #used to label the pattern name


    #===laser parameters===
    POA = []
    numPulses = 0
    beam_duration = 0
    patternid = 0

    def __init__(self, description, odor_obj, opto_obj, POA, numPulses, laserstims, isProbe):

        self.num_lasers = 2 #outdated variable still in use
        self.description = description

        self.odor_obj = odor_obj
        self.opto_obj = opto_obj

        #laser parameters. TODO: streamline if have time!
        self.POA = POA #pulse onset asynchrony: duration between onset of each TTL pulse to DMD chip
        self.numPulses = numPulses  #TTL pulses
        self.laserstims = laserstims

        self.isProbe = isProbe

    def __str__(self,indent = ''):
        return indent+"Stimulus: " + self.description + \
                "\todor: " + str(self.odor_obj.name) + \
                "\tdilution: " + str(self.odor_obj.liq_dilution)+ \
                "\tmfc flows: " + str(self.odor_obj.flow) + \
                "\tPOA: " + str(self.POA) + \
                "\tnumPulses: " + str(self.numPulses) + \
                "\tlaserstims: " + str(self.laserstims)

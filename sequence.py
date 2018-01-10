from copy import deepcopy
from PIL import Image, ImageFont, ImageDraw
import numpy as np
import matplotlib.pyplot as plt
import spot
from random import shuffle, choice
import time_shifter



class Sequence:
     
    frame_switches=[] #timestamps where frame switches
    spotlist=[] #container for spots
    seq=[] #frames in sequence
    img=[] #image of sequence
    isProbe=0 #if sequence is probe trial in task (affects reinforcement)
    label='' #stimulus label e.g. 'AB', 'BA' etc.
    isRandomSequence = False
    excluded_spots=np.array([[-99,-99]])
    included_spots=[]
    mode = '' #grid, freedraw
    
    #unused in older versions (pre 07.2016)
    numPulses = 0 
    POA = []
    
    #used only for ALP
    ALP_seq=[]
    
    #switches
    timing_is_rand=0
    
    def __init__(self,spots,timing,isProbe,rig,spotsizes=[],label='', mode='grid', intensities=[],grouptimes=[],rand_args={}):
        self.rig=rig

        if len(intensities)==0:
            for i in range(len(spots)):
                intensities.append(255)
                
                
        if self.rig=='Polygon':
            self.Im_dim = [684,608] #[ImHeight, ImWidth]
            self.array_dim = self.Im_dim
            self.offset = [0,0] #
            self.scaling = [1.0, 0.5]
        elif self.rig=='ALP':
            self.Im_dim = [56,80]
            self.array_dim = [768,1024]
            self.offset = [340,458]
            self.scaling = [1.0, 1.0]
        elif self.rig=='ALP2':
            self.Im_dim = [768,1024]
            self.array_dim = [768,1024]
            self.offset = [0,0]
            self.scaling = [1.0, 1.0]
            
        else:
            raise ValueError('Rigname ' + rig +' not recognized')
        
        if mode == 'grid':
            self.create_xy_seq(spots,spotsizes,timing,intensities,grouptimes,rand_args,isProbe,rig,label)
        elif mode == 'freedraw':
            self.create_im_seq(spots,timing,intensities,grouptimes,isProbe,rig,label)
        
        if self.rig=='ALP':
            self.calc_TTL()
            #self.calc_ALP_seq()
        
        
    def bin_sequence_1ms(self):
        #bin sequence into 1 millisecond frames. useful for PWM at 1KHz
        frames={}
        for t,im in zip(self.frame_switches,self.seq):
            frames[t]=im
        
        bin_frame_switches=np.arange(0,self.frame_switches[-1]+1)
        bin_seq=[0]*len(bin_frame_switches)
        
        
        fs=list(self.frame_switches)
        fs2=list(self.frame_switches)
        fs2.pop(0)
        fs2.append(fs2[-1]+1)
        fs_range=np.array([fs,fs2]).transpose()
        
        for r1,r2 in fs_range:
            thisframe=frames[r1]
            bin_seq[r1:r2]=[thisframe]*(r2-r1)
            
        self.seq=bin_seq
        self.frame_switches=bin_frame_switches
        
    def calc_TTL(self):
        #set the TTL pulse parameters that will be delivered from arduino to DMD
        #1. number of TTL pulses and 2.pulse onset asynchrony
        POA = np.diff(self.frame_switches)
        POA = np.append(POA,0) #last frame has no offset time                     
        numPulses = len(self.frame_switches)
        
        self.POA = POA
        self.numPulses = numPulses
    
    def calc_ALP_seq(self):
        #**UNUSED 10-18-16**
        #for ALP, frames are specified in bins of ten ms, and a single sequence contains all the frames 
        #original solution was to use sequence queue mode with single frame per sequence, to allow for varying timing
        #however, each sequence takes ~1s to upload
        
        frame_n = self.POA / 10
        DMD_seq=[]
        frame_n[-1] = 1 #we want single frame for last frame (empty)

        for n,frame in zip(frame_n,self.seq):
            self.ALP_seq = self.ALP_seq + [frame]*n

    def createRandomSpot(self,xy_is_rand,timing_is_rand,intensity_is_rand):
        spot_obj = spot.RandomSpot(self.rig,xy_is_rand,timing_is_rand,intensity_is_rand)

        return spot_obj

    def create_xy_seq(self,spots,spotsizes,timing,intensities,grouptimes,rand_args,isProbe,rig,label=''):
        """
        takes list of spot coordinates e.g.[[a1,a2],[b1,b2]]
        and spot timings, [[onseta,offseta],[onsetb,offsetb]]
        creates spot.Spot object for each 
        and then a sequence object to encapsulate
        sequence will be RandomSequence if any spots are random
        """
        min_spacing = 0
        spotlist=[]

        if len(grouptimes)!=len(spots):
            grouptimes=[[]]*len(spots)
        self.rand_args=rand_args
        
        for xy,size,this_timing,this_intensity,grouptime in zip(spots,spotsizes,timing,intensities,grouptimes):
            if xy == ['random']:
                xy_is_rand=True
            else:
                xy_is_rand=False
                
            if xy == ['empty']:
                size = 0
                xy=[0,0]
            
            #to specify random timing, put timing in nested list of bounds
            #[[onset1,onset2],[dur1,dur2]]
            #timing will have random onset in [onset1,onset2] and random duration in [dur1,dur2]
            
            if isinstance(this_timing[0],list) or isinstance(this_timing[1],list): 
                timing_is_rand=True
            else:
                timing_is_rand=False
            
            self.timing_is_rand = timing_is_rand #to be used for grouptimes later
            
            if isinstance(this_intensity,list):
                intensity_is_rand=True
            else:
                intensity_is_rand=False
            
            if xy_is_rand or timing_is_rand or intensity_is_rand:
                spot_obj = self.createRandomSpot(xy_is_rand,timing_is_rand,intensity_is_rand)
    
                if xy_is_rand:
                    spot_obj.init_xy(size,min_spacing)
                else: 
                    spot_obj.set_xy(xy,size)

                if timing_is_rand:
                    spot_obj.timing_bounds = this_timing
                    spot_obj.grouptime = grouptime
                else:
                    spot_obj.set_timing(this_timing)
                    
                if intensity_is_rand:
                    spot_obj.intensity_bounds = this_intensity
                else:
                    spot_obj.set_intensity(this_intensity)
                
    
            else:
                spot_obj = spot.Spot(rig)
                spot_obj.set_xy(xy,size)
                spot_obj.set_timing(this_timing)
                spot_obj.set_intensity(this_intensity)
            
            spotlist.append(spot_obj)

        self.spotlist = spotlist
        self.isProbe = isProbe
        self.label = label

        if (self.rand_args['omit'] > 0) or (self.rand_args['replace'] > 0):
            self.isRandomSequence = True
            self.original_spotlist = deepcopy(spotlist) #create copy for omission/replacement later

        if self.rand_args['scramble'] == 1:
            self.isRandomSequence = True

        if sum(np.array(self.rand_args.values())>0) > 1:
            raise ValueError('More than one rand arg initialized. Check '+self.label)

        if self.rand_args['randt'] > 0: #select different partitions by randt param
            self.isRandomSequence = True
            self.original_spotlist = deepcopy(spotlist) #create copy for timing rand later
            sample_number = self.rand_args['randt']
            self.shifter = time_shifter.partition_shifter(sample_number)

        if self.rand_args['randdur'] > 0: #select different partitions rand dur schemes
            self.isRandomSequence = True
            self.original_spotlist = deepcopy(spotlist) #create copy for timing rand later
            scheme_number = self.rand_args['randdur']
            self.shifter = time_shifter.duration_shifter(scheme_number)



        if any(isinstance(i,spot.RandomSpot) for i in spotlist):
            self.isRandomSequence = True
            self.randomize()
        else:
            self.update()

    def create_im_seq(self,spots,timing,intensities,grouptimes,isProbe,rig,label=''):
        spotlist=[]
        for ptn,this_timing,this_intensity in zip(spots,timing,intensities):
            
            #to specify random timing, put timing in nested list of bounds
            #[[onset1,onset2],[dur1,dur2]]
            #timing will have random onset in [onset1,onset2] and random duration in [dur1,dur2]
            
            xy_is_rand = False
            
            if isinstance(this_timing[0],list) or isinstance(this_timing[1],list): 
                timing_is_rand=True
            else:
                timing_is_rand=False

            
            if isinstance(this_intensity,list):
                intensity_is_rand=True
            else:
                intensity_is_rand=False
            

            if timing_is_rand:
                spot_obj = self.createRandomSpot(xy_is_rand,timing_is_rand,intensity_is_rand)
                spot_obj.timing_bounds=this_timing
            else:
                spot_obj = spot.Spot(rig,)
                spot_obj.set_timing(this_timing)
            
            spot_obj.set_ptn(ptn)
            spot_obj.set_intensity(this_intensity)
            spotlist.append(spot_obj)
            
        if any(isinstance(i,spot.RandomSpot) for i in spotlist):
            self.isRandomSequence=True

        
        self.spotlist = spotlist
        self.isProbe = isProbe
        self.label = label
        
        if self.isRandomSequence:
            self.randomize()
        else:
            self.update()

    
    def image_seq(self):
        """
        create image schematic showing time course of pattern, displayed using sequence.show()
        """
        frame_images=[]
        
        if self.rig == 'Polygon':
            border_width = 10
            textsize = 100
            textpos = (10,10)
        elif self.rig == 'ALP':
            border_width = 1
            textsize = 10
            textpos = (4,2)
        elif self.rig == 'ALP2':
            border_width = 1
            textsize = 10
            textpos = (4,2)


        border_color = 127
        font = ImageFont.truetype("arial.ttf", textsize)
        #font = ImageFont.truetype("/Library/Fonts/Arial Narrow.ttf", textsize) #for MacOSX


        for frame, timestamp in zip(self.seq, self.frame_switches):
            #crop image to stimulation field
            r=[self.offset[0],self.offset[0]+self.Im_dim[0]] #row
            c=[self.offset[1],self.offset[1]+self.Im_dim[1]] #col
            frame = frame[r[0]:r[1],c[0]:c[1]]
            
            #add border to each frame
            frame=np.pad(array=frame,pad_width=border_width,mode='constant',constant_values=border_color)
            
            img=Image.fromarray(frame)
            
            #undo geometric distortions on image
            img=self.image_transform(img)
            
            #add text to image
            draw = ImageDraw.Draw(img)
            draw.text(textpos,str(timestamp),border_color,font=font)
            
            frame_images.append(img)
        
        #combine all frames into single image
        x=0
        
        w = sum(i.size[0] for i in frame_images)
        mh = max(i.size[1] for i in frame_images) #maximum height
        
        combined = Image.new('L', (w,mh))
        for i in frame_images:
            combined.paste(i,(x,0))
            x += i.size[0]
        
        self.img=combined

    def image_transform(self,img):
        """
        pixel images uploaded to DMD may be distorted (e.g. mirror reversal, scaling in Polygon)
        so the final output image will not match the input image
        correct the distortion to create display (not stimulation) images that 
        match what is stimulated    
        """
        
        heightscale=self.scaling[0]
        widthscale=self.scaling[1]
        
        new_height=int(self.Im_dim[0]/heightscale)
        new_width=int(self.Im_dim[1]/widthscale)
    
        img=img.resize((new_width,new_height))
        if self.rig=='Polygon':
            img=img.rotate(90,expand=True)
            img=img.transpose(Image.FLIP_TOP_BOTTOM)
        elif self.rig == 'ALP':
            img=img.rotate(90,expand=True)
            img=img.transpose(Image.FLIP_TOP_BOTTOM)
        
        return img        

    def randomize(self):
        if (self.rand_args['omit'] > 0) or (self.rand_args['replace'] > 0) or \
                (self.rand_args['randt'] > 0) or (self.rand_args['randdur'] > 0):
            self.spotlist = deepcopy(self.original_spotlist)
            
        if not self.isRandomSequence:
            raise ValueError('Trying to randomize non-random sequence!')
            return

        trial_excluded_spots=deepcopy(self.excluded_spots) #include other spots in sequence from excluded spots
                                                    #especially if you want different random spots
        
        if trial_excluded_spots.size == 0:
            trial_excluded_spots=np.array([[-99,-99]])

        #spot replacement -- replace some spots with spatially-random spot (same timing)
        nreplace = self.rand_args['replace']
        if nreplace > 0:
            new_spotlist = deepcopy(self.spotlist)
            shuffle(new_spotlist)
           
            randomSpots=[]
        
            for s in new_spotlist[0:nreplace]:
                xy=s.xy #copy non-spatial (except size) characteristics of spot to be replaced
                gridsize=s.gridsize
                timing=s.timing
                intensity=s.intensity

                newspot = self.createRandomSpot(xy_is_rand=1,timing_is_rand=0,intensity_is_rand=0)
                newspot.init_xy(gridsize=gridsize,min_spacing=0)
                newspot.set_timing(timing)
                newspot.set_intensity(intensity)
                randomSpots.append(newspot)
            
            new_spotlist[0:nreplace] = randomSpots
            self.spotlist=deepcopy(new_spotlist)


        self.rand_xy(trial_excluded_spots)

        #set intensity to the same across all spots (take first spot)
        intensity = self.spotlist[0].intensity
        for this_spot in self.spotlist:
            this_spot.set_intensity(intensity)

        #set timing groups
        group_timings = {}
        if self.timing_is_rand:
            for this_spot in self.spotlist:
                if len(this_spot.grouptime) != 2:
                    continue 
                else:
                    group_number,offset = this_spot.grouptime

                if (offset==0) and (group_number not in group_timings):
                    group_timings[group_number] = this_spot.timing

            for this_spot in self.spotlist:
                if len(this_spot.grouptime) != 2:
                    continue 
                else:
                    group_number,offset = this_spot.grouptime
                    new_timing = list(np.array(group_timings[group_number]) + offset)
                    this_spot.timing = new_timing

        
        #spot omission
        omit = self.rand_args['omit']
        if omit > 0:
            new_spotlist = deepcopy(self.spotlist)
            shuffle(new_spotlist)
            self.spotlist=new_spotlist[0:len(self.original_spotlist)-omit]
            
        #scramble
        if self.rand_args['scramble'] == 1:
            all_timings=[s.timing for s in self.spotlist]
            shuffle(all_timings)
            for s, new_timing in zip(self.spotlist, all_timings):
                s.timing = new_timing

        #randomize timing distance
        if self.rand_args['randt'] > 0:
            shift_map=self.shifter.get_shift_map()

            for s in self.spotlist:

                old_t = tuple(s.timing)
                new_t = shift_map[old_t]
                print old_t,new_t
                s.timing = new_t

        #randomize duration
        if self.rand_args['randdur'] > 0:
            shift_map=self.shifter.get_shift_map()

            for s in self.spotlist:

                old_t = tuple(s.timing)
                new_t = shift_map[old_t]
                print old_t,new_t
                s.timing = new_t

        self.update()

    def rand_xy(self,trial_excluded_spots):
        for this_spot in self.spotlist:

            if isinstance(this_spot, spot.RandomSpot):
                this_spot.excluded_spots=trial_excluded_spots
                this_spot.randomize()

            #add new random spot to excluded spots list to avoid repeats
            trial_excluded_spots=np.vstack([trial_excluded_spots,this_spot.xy])



    def randomize_ephys(self):
        if (self.rand_args['omit'] > 0) or (self.rand_args['replace'] > 0):
            self.spotlist = deepcopy(self.original_spotlist)
            
        if not self.isRandomSequence:
            raise ValueError('Trying to randomize non-random sequence!')
            return

        #spot replacement -- replace some spots with spatially-random spot (same timing)
        nreplace = self.rand_args['replace']
        if nreplace > 0:
            new_spotlist = deepcopy(self.spotlist)
            shuffle(new_spotlist)
           
            randomSpots=[]
        
            rig=self.rig
            for s in new_spotlist[0:nreplace]:
                xy=s.xy #copy non-spatial (except size) characteristics of spot to be replaced
                gridsize=s.gridsize
                timing=s.timing
                intensity=s.intensity
                
                newspot = spot.RandomSpot(rig,xy_is_rand=1,timing_is_rand=0,intensity_is_rand=0)
                newspot.init_xy(gridsize=gridsize,min_spacing=0)
                newspot.set_timing(timing)
                newspot.set_intensity(intensity)
                randomSpots.append(newspot)
            
            new_spotlist[0:nreplace] = randomSpots
            self.spotlist=deepcopy(new_spotlist)


        trial_included_spots=deepcopy(self.included_spots) #include other spots in sequence from excluded spots
                                                    #especially if you want different random spots

        for this_spot in self.spotlist:
        
            if isinstance(this_spot, spot.RandomSpot):
                this_spot.included_spots=trial_included_spots                
                this_spot.randomize_ephys()
            

            
        
        #set intensity to the same across all spots (take first spot)
        intensity = self.spotlist[0].intensity
        for this_spot in self.spotlist:
            this_spot.set_intensity(intensity)
        

        #set timing groups
        group_timings = {}
        if self.timing_is_rand:
            for this_spot in self.spotlist:
                if len(this_spot.grouptime) != 2:
                    continue 
                else:
                    group_number,offset = this_spot.grouptime

                if (offset==0) and (group_number not in group_timings):
                    group_timings[group_number] = this_spot.timing

            for this_spot in self.spotlist:
                if len(this_spot.grouptime) != 2:
                    continue 
                else:
                    group_number,offset = this_spot.grouptime
                    new_timing = list(np.array(group_timings[group_number]) + offset)
                    this_spot.timing = new_timing

        
        #spot omission
        omit = self.rand_args['omit']
        if omit > 0:
            new_spotlist = deepcopy(self.spotlist)
            shuffle(new_spotlist)
            self.spotlist=new_spotlist[0:len(self.original_spotlist)-omit]
            
        #scramble
        if self.rand_args['scramble'] == 1:
            all_timings=[s.timing for s in self.spotlist]
            shuffle(all_timings)
            for s, new_timing in zip(self.spotlist, all_timings):
                s.timing = new_timing

        self.update()
        
    def rand_intensity_hacky(self,mode='halftone'):
        #hacky solution for setting intensity of patterns, manually set here
        intensities = [9, 47, 70, 94, 255]
        #Polygon2 4x -- 9: 2mW/mm2, 47:10mW/mm2, 70: 15mW/mm2, 94:20mW/mm2, 255: 54mW/mm2
        
        intensity = choice(intensities)

        for this_spot in self.spotlist:
            this_spot.ptn_small2DMD() #reset intensities to 255
            
            if mode == 'PWM':
                this_spot.set_intensity(intensity)
            elif mode == 'halftone':
                this_spot.set_intensity_halftone(intensity)
                
        self.update()
        
    def set_intensity(self, intensity, mode='PWM'):
        for this_spot in self.spotlist:
            this_spot.ptn_small2DMD() #reset intensities to 255
            
            if mode == 'PWM':
                this_spot.set_intensity(intensity)
            elif mode == 'halftone':
                this_spot.set_intensity_halftone(intensity)        
        
        
        self.update()
            
    def show(self):
        self.image_seq()
        plt.imshow(self.img)
        plt.show()

    
    def update(self):
        """

        mode -- grid: spots in grid mode, have to be converted to pixels
                pix: spots in pixel mode   
        """
        
        nspots=len(self.spotlist)
        
        spot_timing=[]
        for this_spot in self.spotlist:
            spot_timing.append(this_spot.timing)
        
        spot_timing=np.array(spot_timing)
        
        frame_switches = np.unique(spot_timing)
        
        if not (0 in frame_switches):
            frame_switches=np.insert(frame_switches,0,0) #if no frame starts from 0, need empty frame at beginning
        
        frame_array=np.zeros([nspots,len(frame_switches)]) 
        #array of binary values, row is spot number, column is frame switch
        #1 means spot is present in *after* that frame switch
        

        for i in range(len(frame_switches)):
            switch_time = frame_switches[i]
            spots_present = (switch_time >= spot_timing[:,0]) * (switch_time < spot_timing[:,1]) 
            frame_array[:,i] = spots_present
        
        #create sequence of frames
        seq=[]
        for i in range(len(frame_switches)):
            #start with empty frame
            frame = np.zeros([self.array_dim[0],self.array_dim[1]])
            spots_present = frame_array[:,i]
            spots_present = np.where(spots_present==True)[0]
            spots_in_frame = [self.spotlist[x] for x in spots_present]

            for j in spots_in_frame:
                frame = frame + j.ptn
                    
            #handle overlapping spots -- normalize all pixel values to 255
            frame[frame>255]=255
            
            seq.append(frame)
        
        self.seq=seq
        self.frame_switches=frame_switches
        self.calc_TTL()
        
        #self.image_seq()

class Sequence2(Sequence):
    def __init__(self,spots,timing,isProbe,rig,spotsizes=[],label='', mode='grid', intensities=[],grouptimes=[],rand_args={}):
        self.rand_spotlist=[]
        Sequence.__init__(self,
                          spots=spots,
                          timing=timing,
                          isProbe=isProbe,
                          rig=rig,
                          spotsizes=spotsizes,
                          label=label,
                          mode=mode,
                          intensities=intensities,
                          grouptimes=grouptimes,
                          rand_args=rand_args)



    #call RandomSpot2 instead of RandomSpot, randomization by spotlist
    def createRandomSpot(self,xy_is_rand,timing_is_rand,intensity_is_rand):
        spot_obj = spot.RandomSpot2(self.rig,xy_is_rand,timing_is_rand,intensity_is_rand)

        return spot_obj

    def rand_xy(self,foo):
        trial_rand_spotlist=deepcopy(self.rand_spotlist)
        for this_spot in self.spotlist:
            if isinstance(this_spot, spot.RandomSpot2):
                if len(trial_rand_spotlist) == 0:
                    print 'Not enough spots in randomize xy list. Error'
                    trial_rand_spotlist=[(0,0)]

                this_spot.rand_spotlist=trial_rand_spotlist
                this_spot.randomize()

            #remove decided spot from random list, to avoid repeats
            thisxy = tuple(this_spot.xy)
            if thisxy in trial_rand_spotlist:
                trial_rand_spotlist.remove(thisxy)
            else:
                print 'WARNING! Randomized spot not from spotlist. How???'



def create_empty_seq(rig):
    #empty pattern stimulation: just create a spot of 0 duration (dirty)
    spots = [[0,0]]
    timing = [[0,0]]
    isProbe = 0
    label = 'DMDoff'
    spotsizes = [10]
    intensities = [255]

    rand_args = {} #initialize dictionary of global sequence parameters
    #
    for p in ['omit','replace','scramble','randt','randdur']:
        rand_args[p]=0

    seq = Sequence(spots = spots,
                   spotsizes = spotsizes,
                   timing = timing,
                   intensities = intensities,
                   isProbe = isProbe,
                   rig = rig,
                   label = label, 
                   mode='grid',
                   rand_args=rand_args)
    
    return seq


def strobify(img,timing,strobe_on,strobe_off):
    strobe={}
    strobe['on']=strobe_on #stim on duration in ms
    strobe['off']=strobe_off
    strobe['period']=strobe['on']+strobe['off']

    strobe_img=[]
    strobe_timing=[]

    for i,t in zip(img,timing):
        strobe['duration']=t[1]-t[0]
        strobe['cycles']=int(np.floor(strobe['duration'] / strobe['period']))

        #==create strobe pulses and append to containers==
        for c in range(strobe['cycles']):
            c_start = t[0]+c*strobe['period']
            c_end = c_start + strobe['on']
            strobe_timing.append([c_start,c_end])
            strobe_img.append(i)    
    
    return strobe_img,strobe_timing


#===TODO: shift this function out of the main voyeur function to here (clean up reference to 'self.spots')
def get_gridpattern_params(ptn,sessNow):
    #retrieve xy and timing
    xy=[]
    timing=[]
    for spotLetter in sessNow['patterns'][ptn]:
        onset= sessNow['patterns'][ptn][spotLetter]['onset']
        dur=sessNow['patterns'][ptn][spotLetter]['dur']

        if spotLetter.startswith('R'):
            xy.append(self.spots['list']['R'])
            timing.append([onset,dur])
        else:
            xy.append(self.spots['list'][spotLetter])
            offset=onset+dur
            timing.append([onset,offset])
    return xy, timing

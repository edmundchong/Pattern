from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from random import randint,choice

class Spot:
    timing=[]
    xy=[]
    intensity=255
    grouptime = []

    
    gridsize=0
    #camleft: x+, camright:x-, camup: y+, camdown: y-
    def __init__(self,rig):
        self.rig=rig
        if self.rig=='Polygon':
            self.Im_dim = [684,608] #[ImHeight, ImWidth]
            self.array_dim = self.Im_dim
            self.offset = [0,0] #
            self.scaling = [1.0, 0.5]
        elif self.rig=='ALP':
            self.Im_dim = [56,80]
            self.array_dim = [768,1024]
            self.offset = [340,457]
            self.scaling = [1.0, 1.0]
        else:
            raise ValueError('Rigname ' + rig +' not recognized')
        
        self.gridsize=0
        self.ptn=np.zeros(self.array_dim)
        self.ptn_small=np.zeros(self.Im_dim)
    def get_grid_max(self,gridsize):
        #returns max (x,y) coordinates for grid of given square size
        #note zero-indexing
        height_scale=self.scaling[0]
        width_scale=self.scaling[1]
    
        #transform to pixel size
        height=max(np.floor(gridsize * height_scale), 1) #must be >0
        width=max(np.floor(gridsize * width_scale), 1) #must be >0
        
        y_max = np.floor(self.Im_dim[0] / height) #number of spots in one (image) column but (projected image) row        
        x_max = np.floor(self.Im_dim[1] / width) #number of spots in one (image) row but (projected image) column
        
        x_max= int(x_max - 1) #zero-indexing
        y_max= int(y_max - 1)
        
        return x_max, y_max

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
            
        return img        
    
    def ptn_small2DMD(self):
        #go from ptn_small to DMD array pattern. two purposes:
        #(1) in ALP, only subset of DMD is used. the pattern is defined 
        #    within this subspace, then redefined as part of the whole DMD array
        #(2) in intensity randomization, intensities may go to zero. 
        #    ptn_small always has pixels on at 255, so the full pattern is ptn_small * new_intensity
    
        r=[self.offset[0],self.offset[0]+self.Im_dim[0]]
        c=[self.offset[1],self.offset[1]+self.Im_dim[1]]
        self.ptn=np.zeros(self.array_dim) #reset pattern
        self.ptn[r[0]:r[1],c[0]:c[1]]=self.ptn_small
        
        return  
    
    
    def set_intensity(self,intensity):
        self.ptn = (self.ptn > 0) * intensity 
        self.intensity=intensity
        return
    
    def set_intensity_halftone(self,intensity):
        self.ptn_small2DMD() #reset intensities to 255
        pixOnInd=np.ravel_multi_index(np.where(self.ptn==255),self.Im_dim)
        n=len(pixOnInd)
        nOff=int(round(n*(1-intensity/255.0)))
        pixOffInd=np.random.permutation(pixOnInd)[0:nOff]
        pixOffInd=np.unravel_index(pixOffInd,self.Im_dim)
        self.ptn[pixOffInd]=0
        self.intensity=intensity
                
        

    def set_ptn(self,ptn):
        #directly set image array of spot
        self.ptn_small=ptn
        self.ptn_small2DMD()
      
    
    def set_timing(self,timing):
        """
        timing = [onset,offset]
        defines when the spot is present in sequence
        """
        self.timing=[timing[0],timing[1]]

    def set_xy(self,xy,gridsize):
        """
        xy=[x,y]
        each square is assigned a coordinate (x,y), starting from top left (0,0)
        some pixels will be left over on bottom right
        function converts (x,y) --> 2D array of pixel values
        ***NOTE that x, y are cartesian coordinates. this is swapped from matrix indices!! (confusing)
        an additional swap is made because the projected image is rotated from the original matrix, so your 
        x, y is now rotated and flipped
        """
        
        x=xy[0]
        y=xy[1]
        
        height_scale = self.scaling[0]
        width_scale  = self.scaling[1]
    
        #transform to pixel size
        height=np.floor(gridsize * height_scale)
        width=np.floor(gridsize * width_scale)
        x_max,y_max=self.get_grid_max(gridsize)
        if (x > x_max) or (y > y_max):
            print 'x is: '+str(x)+' y is: '+str(y)+', x_max is '+str(x_max)+' y_max is '+str(y_max)
            raise ValueError('set_xy: x or y coordinate is greater than max')
    
        topleft = [y*height,x*width] #here the swap from cartesian to matrix is confusing
        bottomright = [(y+1)*height-1,(x+1)*width-1]
        
        ptn=np.zeros(self.Im_dim)
        ptn[topleft[0]:bottomright[0]+1,topleft[1]:bottomright[1]+1]=255
        
        self.ptn_small=ptn
        self.ptn_small2DMD()
    
        self.gridsize=gridsize
        self.xy=[x,y]
    
    def set_xy_pix(self,xy,ring=0):
        #set single pixel x,y
        x = xy[0]
        y = xy[1]
        
        ptn=np.zeros(self.Im_dim)
        ptn[x,y]=255
        
        xmax = self.Im_dim[0]
        ymax = self.Im_dim[1]
        #add a ring of pixels surrounding the given pixel as center
        #Polygon single pixel is too dim under camera for calibration
        if ring > 0:
            for i in range(-ring,ring+1):
                for j in range(-ring,ring+1):
                    new_x = x+i
                    new_y = y+j
                    new_x = min(max(0,new_x),xmax-1) #boundary conditions
                    new_y = min(max(0,new_y),ymax-1)
                    #print 'i: '+str(i)+' j: '+str(j)
                    #print new_x,new_y
                    ptn[new_x,new_y]=255
        
        self.ptn_small=ptn
        self.ptn_small2DMD()
    
        self.xy=[x,y]      
        
    
    def show(self,fullField=True):
        if fullField==True:
            img=Image.fromarray(self.ptn)
        else:
            img=Image.fromarray(self.ptn_small)
        
        img=self.image_transform(img)
        plt.imshow(img)
        plt.show()
        
class RandomSpot(Spot):
    xy_is_rand = False
    excluded_spots=np.array([[-99,-99]]) #should be np array
    included_spots=[]
    
    min_spacing = -99 #minimum euclidean distance that random spots should be from excluded spots
                      #distance measured in spots (e.g. 1 means 1 spot length) 
    
    
    timing_is_rand = False
    timing_bounds = [[],[]]
    #for random timing, specify timing_bounds as nested list [[a,b],[c,d]]
    #spot onset will be random between a & b (inclusive of both)
    #spot offset will be random between c & d (inclusive of both)
    
    intensity_is_rand = False
    intensity_bounds = [] #[lower,upper,graylevel]
        
    
    def __init__(self,rig,xy_is_rand,timing_is_rand,intensity_is_rand):
        Spot.__init__(self,rig)
        self.xy_is_rand = xy_is_rand
        self.timing_is_rand = timing_is_rand
        self.intensity_is_rand = intensity_is_rand
    
    
    def init_xy(self,gridsize,min_spacing):
        self.gridsize=gridsize
        self.min_spacing=min_spacing
        
    def randomize(self):

        if self.xy_is_rand:
            self.rand_xy()
        if self.timing_is_rand:
            self.rand_timing()
        
        
        if self.intensity_is_rand:
            self.rand_intensity()
        else:
            self.set_intensity(self.intensity)
            
            
    def randomize_ephys(self):

        if self.xy_is_rand:
            self.rand_xy_ephys()
        if self.timing_is_rand:
            self.rand_timing()
        
        
        if self.intensity_is_rand:
            self.rand_intensity()
        else:
            self.set_intensity(self.intensity)            

    def rand_intensity(self):
        
        levels = 2**8
        stepsize = 255 / (levels - 1)
        intensity_steps = np.arange(levels) * stepsize
        
        
        intensity = randint(self.intensity_bounds[0],self.intensity_bounds[1])
        intensity = min(intensity_steps, key=lambda x:abs(x-intensity))
        


        self.ptn_small2DMD() #reset intensities to 255
        self.set_intensity(intensity)

            
    def rand_timing(self,resolution = 10):
        #randomize timing with resolution (default is 10ms)
        #TODO: check that timing is nested list [[a,b],[c,d]]
        onsetBounds=self.timing_bounds[0]
        durBounds=self.timing_bounds[1]

        #===randomize onset===
        onset_choices = range(onsetBounds[0],onsetBounds[1]+1,resolution)
        onset = choice(onset_choices)

        #===randomize duration===
        dur_choices = range(durBounds[0],durBounds[1]+1,resolution)
        dur = choice(dur_choices)

        self.set_timing([onset,onset+dur])

    def rand_xy(self):
        if self.gridsize==0:
            raise ValueError('ERROR: **SET GRIDSIZE FIRST!**')
        
        if self.min_spacing==-99:
            raise ValueError('ERROR: SET MIN_SPACING')
        
        x_max,y_max=self.get_grid_max(self.gridsize)
        if self.excluded_spots.shape==(2L,):
            self.excluded_spots=self.excluded_spots.reshape(1L,2L) #if only one spot, need to reshape for concatenation later
            
        new_spots=np.zeros((1,2)).astype(int) - 99 #container holding all spot values, initialized to -99 (to avoid affecting distance calc)
            
        max_loop=10000
        all_spots=np.concatenate([new_spots, self.excluded_spots],axis=0)
        for j in range(max_loop):
            x=randint(0,x_max)
            y=randint(0,y_max)
            
            euclid_dist=np.sqrt(np.sum((all_spots-[x,y])**2,1))
            if euclid_dist.min() > self.min_spacing: 
                new_spots[0,:]=[x,y]
                break
            elif j==max_loop-1:
                raise ValueError('max iterations reached, no possible spot found')
                
        self.xy=[new_spots[0,0], new_spots[0,1]]
        self.set_xy(self.xy,self.gridsize)
        
    def rand_xy_ephys(self):
        if self.gridsize==0:
            raise ValueError('ERROR: **SET GRIDSIZE FIRST!**')
                
        self.xy=choice(self.included_spots)
        self.set_xy(self.xy,self.gridsize)     

        

import numpy as np, bunch
from enlib import scan, rangelist, coordinates, utils

def rand_srcs(box, nsrc, amp, fwhm):
	pos  = np.array([np.random.uniform(box[0,1],box[1,1],nsrc),np.random.uniform(box[0,0],box[1,0],nsrc)]).T
	amps = np.random.exponential(scale=amp, size=nsrc)
	pos_angs = np.random.uniform(0, np.pi, nsrc)
	pos_fracs = np.random.uniform(0, 1, nsrc)
	pos_comps = np.zeros([nsrc,4])
	pos_comps[:,0] = 1
	pos_comps[:,1] = np.cos(2*pos_angs)*pos_fracs
	pos_comps[:,2] = np.sin(2*pos_angs)*pos_fracs
	amps = amps[:,None]*pos_comps
	return bunch.Bunch(pos=pos,amps=amps,beam=fwhm/(8*np.log(2))**0.5)

def white_noise(ndet, nsamp, sigma, seed=0):
	noise = bunch.Bunch(
		bins  = np.array([[0,nsamp/2+1]]),
		vbins = np.array([[0,0]]),
		iNu   = np.zeros([1,ndet])+sigma**-2,
		Q     = np.zeros([1,ndet]),
		seed  = seed,
		sigma  = sigma)
	return noise

def scan_ceslike(nsamp, box, sys="equ", srate=100, azrate=0.123):
	t = np.arange(nsamp,dtype=float)/srate
	boresight = np.zeros([nsamp,3])
	boresight[:,0] = t
	boresight[:,1] = box[0,1]+(box[1,1]-box[0,1])*(1+np.cos(2*np.pi*t*azrate))/2
	boresight[:,2] = box[0,0]+(box[1,0]-box[0,0])*np.arange(nsamp)/nsamp
	return bunch.Bunch(boresight=boresight, sys=sys)

def scan_grid(box, res, sys="equ"):
	n = (np.asarray(box[1]-box[0])/res).astype(int)
	dec = np.linspace(box[0,0],box[1,0],n[0])
	ra  = np.linspace(box[0,1],box[1,1],n[1])
	decra = np.empty([2,dec.size,ra.size])
	decra[0] = dec[:,None]
	decra[1] = ra [None,:]
	decra = decra.reshape(2,-1)
	t = np.arange(decra.shape[1])*1e3/decra.shape[1]
	boresight = np.empty([t.size,3])
	boresight[:,0] = t
	boresight[:,1:] = decra.T
	return bunch.Bunch(boresight=boresight, sys=sys)

def dets_scattered(ndet, rad=0.5*np.pi/180):
	offsets = np.random.standard_normal([ndet,3])*rad
	offsets[:,0] = 0
	# T,Q,U sensitivity
	angles = np.arange(ndet)*np.pi/ndet
	comps     = np.zeros([ndet,4])
	comps[:,0] = 1
	comps[:,1] = np.cos(2*angles)
	comps[:,2] = np.sin(2*angles)
	return bunch.Bunch(comps=comps, offsets=offsets)

def nocut(ndet, nsamp):
	return rangelist.Multirange([rangelist.Rangelist(np.zeros([0,2],dtype=int),n=nsamp) for i  in range(ndet)])

class SimSrcs(scan.Scan):
	def __init__(self, scanpattern, dets, srcs, noise):
		# Set up the telescope
		self.boresight = scanpattern.boresight
		self.sys       = scanpattern.sys
		self.offsets   = dets.offsets
		self.comps     = dets.comps
		self.cut       = nocut(self.ndet,self.nsamp)
		self.site      = None
		self.mjd0      = 0
		# Set up the simulated signal properties
		self.srcs  = srcs
		self.noise = noise

	def get_samples(self):
		# Start with the noise
		np.random.seed(self.noise.seed)
		tod = np.random.standard_normal([self.ndet,self.nsamp])*self.noise.sigma
		# And add the point sources
		for di in range(self.ndet):
			print di
			for i, (pos,amp) in enumerate(zip(self.srcs.pos,self.srcs.amps)):
				point = (self.boresight+self.offsets[di,None,:])[:,1:]
				r2 = np.sum((point-pos[None,:])**2,1)/self.srcs.beam**2
				I  = np.where(r2 < 6**2)[0]
				tod[di,I] += np.exp(-0.5*r2[I])*np.sum(amp*self.comps[di])
		return tod

	def get_model(self, point):
		res = np.zeros([point.shape[0],self.srcs.amps.shape[1]])
		for i, (pos,amp) in enumerate(zip(self.srcs.pos,self.srcs.amps)):
			r2 = np.sum((point-pos[None,:])**2,1)/self.srcs.beam**2
			I  = np.where(r2 < 6**2)[0]
			res[I,:] += np.exp(-0.5*r2[I])[:,None]*amp[None,:]
		return res

	def __getitem__(self, sel):
		res, detslice, sampslice = self.getitem_helper(sel)
		return res
"""
This script sets up an afferent inhomogenous Poisson process onto the populations
"""
import brian2, string
import numpy as np

import sys
sys.path.append('../../')
from ntwk_build.syn_and_connec_construct import build_populations,\
    build_up_recurrent_connections,\
    initialize_to_rest
from ntwk_build.syn_and_connec_library import get_connectivity_and_synapses_matrix
from ntwk_stim.waveform_library import double_gaussian, ramp_rise_then_constant
from ntwk_stim.connect_afferent_input import construct_feedforward_input
from common_libraries.data_analysis.array_funcs import find_coincident_duplicates_in_two_arrays

import pprint

def run_sim(args):
    ### SIMULATION PARAMETERS

    brian2.defaultclock.dt = args.DT*brian2.ms
    t_array = np.arange(int(args.tstop/args.DT))*args.DT

    NTWK = [{'name':'exc', 'N':args.Ne, 'type':'AdExp'},
            {'name':'inh', 'N':args.Ni, 'type':'LIF'}]
    AFFERENCE_ARRAY = [{'Q':args.Qe_ff, 'N':args.Ne, 'pconn':args.pconn},
                       {'Q':args.Qe_ff, 'N':args.Ne, 'pconn':args.pconn}]
    
    EXC_ACTS, INH_ACTS, SPK_TIMES, SPK_IDS = [], [], [], []

    rate_array = ramp_rise_then_constant(t_array, 0., 0., 0, args.fext)
    M = get_connectivity_and_synapses_matrix('', number=len(NTWK)*3)

    # Manually construct the 6 by 6 matrix:
    for key, val in zip(['Q', 'pconn', 'Erev', 'Tsyn'], [args.Qe, args.pconn, 0., 5.]):
        # recurrent exc-exc and exc-inh connection !
        for m in [M[0,0], M[2,2], M[4,4], M[0,1], M[2,3], M[4,5]]:
            m[key] = val
    for key, val in zip(['Q', 'pconn', 'Erev', 'Tsyn'], [args.Qe_ff, args.pconn, 0., 5.]):
        # recurrent exc-exc, exc-inh and feedforward connection !
        for m in [M[0,2], M[2,4]]:
            m[key] = val
    for key, val in zip(['Q', 'pconn', 'Erev', 'Tsyn'], [args.Qi, args.pconn, -80., 5.]):
        # recurrent inh.
        for m in [M[1,1], M[3,3], M[5,5], M[1,0], M[3,2], M[5,4]]:
            m[key] = val
    
    # over various stims...
    EXC_ACTS_ACTIVE1, EXC_ACTS_ACTIVE2, EXC_ACTS_ACTIVE3  = [], [], []
    EXC_ACTS_REST1, EXC_ACTS_REST2, EXC_ACTS_REST3  = [], [], []

    seed = 3
    for EXC_ACTS1, EXC_ACTS2, EXC_ACTS3, FEXT in zip([EXC_ACTS_ACTIVE1,EXC_ACTS_REST1],
                                                     [EXC_ACTS_ACTIVE2,EXC_ACTS_REST2],
                                                     [EXC_ACTS_ACTIVE3,EXC_ACTS_REST3],
                                                     [args.fext, 0.]):

        rate_array = FEXT + double_gaussian(t_array, args.stim_start,\
                                      args.stim_T0, args.stim_T1, args.fext_stim)
        
        POPS, RASTER, POP_ACT = build_populations(NTWK, M, with_raster=True, with_pop_act=True)
        
        initialize_to_rest(POPS, NTWK) # (fully quiescent State as initial conditions)

        AFF_SPKS, AFF_SYNAPSES = construct_feedforward_input(POPS,
                                                             AFFERENCE_ARRAY,\
                                                             t_array,
                                                             rate_array,\
                                                             pop_for_conductance='A',
                                                             SEED=seed)
        
        SYNAPSES = build_up_recurrent_connections(POPS, M, SEED=seed+1)

        net = brian2.Network(brian2.collect())
        # manually add the generated quantities
        net.add(POPS, SYNAPSES, RASTER, POP_ACT, AFF_SPKS, AFF_SYNAPSES) 
        net.run(args.tstop*brian2.ms)

        EXC_ACTS1.append(POP_ACT[0].smooth_rate(window='flat',\
                                                       width=args.smoothing*brian2.ms)/brian2.Hz)
        EXC_ACTS2.append(POP_ACT[2].smooth_rate(window='flat',\
                                               width=args.smoothing*brian2.ms)/brian2.Hz)
        EXC_ACTS3.append(POP_ACT[4].smooth_rate(window='flat',\
                                               width=args.smoothing*brian2.ms)/brian2.Hz)
    np.savez(args.filename, args=args,
             EXC_ACTS_ACTIVE1=np.array(EXC_ACTS_ACTIVE1), EXC_ACTS_ACTIVE2=np.array(EXC_ACTS_ACTIVE2), EXC_ACTS_ACTIVE3=np.array(EXC_ACTS_ACTIVE3),
             EXC_ACTS_REST1=np.array(EXC_ACTS_REST1), EXC_ACTS_REST2=np.array(EXC_ACTS_REST2), EXC_ACTS_REST3=np.array(EXC_ACTS_REST3),
             NTWK=NTWK, t_array=t_array,
             rate_array=rate_array, AFFERENCE_ARRAY=AFFERENCE_ARRAY,
             plot=get_plotting_instructions())

def get_plotting_instructions():
    return """
args = data['args'].all()
fig, AX = plt.subplots(1, figsize=(5,3))
plt.subplots_adjust(left=0.15, bottom=0.15, wspace=0.2, hspace=0.2)
f_ext = np.linspace(args.fext_min, args.fext_max, args.nsim)
mean_exc_freq = []
for exc_act in data['EXC_ACTS']:
    print(exc_act[int(args.tstop/2/args.DT)+1:].mean())
    mean_exc_freq.append(exc_act[int(args.tstop/2/args.DT)+1:].mean())
AX.plot(f_ext, mean_exc_freq, 'k-')
set_plot(AX, xlabel='drive freq. (Hz)', ylabel='mean exc. (Hz)')
"""


if __name__=='__main__':
    import argparse
    # First a nice documentation 
    parser=argparse.ArgumentParser(description=
     """ 
     Investigates what is the network response of a single spike 
     """
    ,formatter_class=argparse.RawTextHelpFormatter)

    # simulation parameters
    parser.add_argument("--DT",help="simulation time step (ms)",type=float, default=0.1)
    parser.add_argument("--tstop",help="simulation duration (ms)",type=float, default=200.)
    parser.add_argument("--nsim",help="number of simulations (different seeds used)", type=int, default=3)
    parser.add_argument("--smoothing",help="smoothing window (flat) of the pop. act.",type=float, default=0.5)
    # network architecture
    parser.add_argument("--Ne",help="excitatory neuron number", type=int, default=4000)
    parser.add_argument("--Ni",help="inhibitory neuron number", type=int, default=1000)
    parser.add_argument("--pconn", help="connection proba", type=float, default=0.05)
    parser.add_argument("--Qe", help="weight of excitatory spike",type=float,default=1.)
    parser.add_argument("--Qe_ff", help="weight of excitatory spike FEEDFORWARD", type=float, default=3.)
    parser.add_argument("--Qi", help="weight of inhibitory spike",type=float,default=5.)
    parser.add_argument("--fext",help="baseline external drive (Hz)",type=float,default=8.)
    parser.add_argument("--fext_stim",help="baseline external drive (Hz)",type=float,default=8.)
    parser.add_argument("--stim_start", help="time of the start for the additional spike (ms)", type=float, default=100.)
    parser.add_argument("--stim_T0",help="we multiply the single spike on the trial at this (ms)",type=float, default=10.)
    parser.add_argument("--stim_T1",help="we multiply the single spike on the trial at this (ms)",type=float, default=20.)
    # stimulation (single spike) properties
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-u", "--update_plot", help="plot the figures", action="store_true")
    parser.add_argument("--filename", '-f', help="filename",type=str, default='data.npz')
    args = parser.parse_args()

    if args.update_plot:
        data = dict(np.load(args.filename))
        data['plot'] = get_plotting_instructions()
        np.savez(args.filename, **data)
    else:
        run_sim(args)
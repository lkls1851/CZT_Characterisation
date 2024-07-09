import numpy as np
from astropy.table import Table
import glob
import os
import sys


def data2fits(infile, outfile):
    with open(infile, 'r') as f:
        l1 = f.readline()
        # print(l1)

    biglist = l1[1:-1].split(",")
    event_data = np.array(biglist, dtype=np.uint64)
    timestamp = np.uint32((event_data & 0xffffffff00000000) >> 32)
    det_id = np.int16((event_data & 0x00000000ff000000) >> 24)
    pix_id = np.int16((event_data & 0x0000000000ff0000) >> 16)
    energy = np.int16((event_data & 0x000000000000ffff) >> 0)

    tab = Table(data=(timestamp, det_id, pix_id, energy), names=("time", "detid", "pixid", "pha"))
    tab.write(outfile)

    # df = pd.DataFrame(data=np.array([timestamp, det_id, pix_id, energy]).T, 
    #                   columns=("time", "detid", "pixid", "pha"))
    # detdata = df.groupby(df['detid'])


if __name__ == "__main__":
   
    basepath = "20240220_det_500040_5_NA_-600_0.372_9_bkg_1000_19.94_run_Y.txt"      # 'expt_data/20230829'
    maxcount = -1               # Set <=0 if all files are to be processed, else end after this
    # infile = '20230628_1418_am_stc1_2_50pkts_ext_hv_spectra.txt'

    for count, infile in enumerate(glob.glob1(basepath, "*.txt")):
        # print(count)
        if count == maxcount:
            print(f"Stopping the loop, max count {maxcount} reached")
            break
        outfile = os.path.join(basepath, infile.replace(".txt", ".fits"))
        if not os.path.exists(outfile):
            print(f"Converting {infile} to {outfile}")
            data2fits(os.path.join(basepath, infile), outfile)
        else:
            print(f"Skipping {infile}: {outfile} already exists.")
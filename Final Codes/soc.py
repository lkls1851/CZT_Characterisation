import http.client as httplib
import serial
from pynq import PL, Overlay
from pynq import allocate
import new_det_data_acquisition_common as common
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import time
import os
import socket
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from datetime import datetime
from astropy.io import fits
from collections import defaultdict
import matplotlib.patches as patches

'''
Define the Thermal Chamber server settings
'''

ip = '192.186.0.113'
port = 502

'''
Define Thermal Chamber registers
'''
register_address_map = {"TEMP_PV": 0,
                        "RH_PV": 2,
                        "RH_SV_Read_Only": 3,
                        "Program_Status": 4,
                        "TEMP_SV": 7,
                        "RH_SV_Read_Write": 16
                        }
coil_address_map = {"Profile_Run": 0,
                    "Lamp_Command": 1,
                    "Manual_Run": 2,
                    "Batch_Start_Flag": 3
                    }

'''
Connect Modbus client
'''
client = ModbusTcpClient(host=ip, port=port)
try:
    connection = client.connect()
    print("Connection successful")
except ConnectionException as e:
    print(f"Connection failed: {e}")

ov = Overlay("./overlays/test_2det_commanding.bit")
czt = ov.AXI_CZT_AXIS_1.AXI_CZT_Controller

reset_pl = ov.Reset_system.reset_gpio.channel1[0].on
dma_channel = ov.DMA.axi_dma_0.recvchannel
wr_data_count = ov.AXIS_Combine.axi_gpio_0.channel1.read
rd_data_count = ov.AXIS_Combine.axi_gpio_0.channel2.read

reset_pl()
test_reply_commands = ['READ_SERIAL_LSB',
                       'READ_SERIAL_MSB',
                       'READ_FIRMWARE_VERSION',
                       'READ_MODULE_VERSION',
                       'EEPROM_CHECKSUM',
                       'GET_CLOCK',
                       'GET_EMULATOR',
                       'GET_GPIO',
                       'GET_PEAKING_TIME',
                       'GET_THRESHOLD',
                       'READ_TEMPERATURE',
                       'READ_STATUS']


path_to_fits_file=''

def noisy_pixels(arr):
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    arr=arr.reshape(-1,1)
    noise=[]
    for i in range(len(arr)):
        if int(arr[i].any())>=upper_bound or int(arr[i].any())<=lower_bound:
            noise.append(i)
    return noise


def data(data_file):
    file = fits.open(data_file)
    file_data = file[1].data
    detector = file_data['detid']
    time = file_data['time']
    pixid = file_data['pixid']
    pha = file_data['pha']
    count0 = dict()
    count1 = dict()
    for i in range(len(detector)):
        pixval = pixid[i]
        if detector[i] == 0:
            if pixval not in count0:
                count0[pixval] = 0
            count0[pixval] += 1
        else:
            if pixval not in count1:
                count1[pixval] = 0
            count1[pixval] += 1

    det0 = []
    for i in range(256):
        if i in list(count0.keys()):
            det0.append(count0[i])
        else:
            det0.append(0)
    nparr = np.array(det0)
    nparr = nparr.reshape((16, 16))
    det1 = []
    for i in range(256):
        if i in list(count1.keys()):
            det1.append(count1[i])
        else:
            det1.append(0)

    nparr = np.array(det1)
    nparr = nparr.reshape((16, 16))
    return nparr


data_arr=data(path_to_fits_file)
q1, q3 = np.percentile(data, [25, 75])
iqr = q3 - q1
lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr
data=data.reshape(-1,1)
noise=[]
for i in range(len(data)):
    if int(data[i])>=upper_bound or int(data[i])<=lower_bound:
        noise.append(i)

## noise is the array containing noisy pixels

for el in noise:
    czt.disable_channel(el)

czt.scan_all_channels()



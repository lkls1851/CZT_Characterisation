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


class color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


ip = '192.186.0.113'
port = 502


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


client = ModbusTcpClient(host=ip, port=port)
try:
    connection = client.connect()
    if connection:
        print("Connection successful")
    else:
        print("Connection failed")
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

def generate_data(date, curr_time, radiation_measured):
    '''
    This function will generate txt files for the data of the experiment
    '''

    ## For executing this line twice, we use for loop
    for _ in range(2):
        det_serial_number = czt.read_serial()

    czt.command("BREAK")
    czt.scan_all_channels()
    if czt.num_disabled > 0:
        for i in czt.disabled_channel_list:
            czt.enable_channel(i)
    else:
        pass

    event_data_buffer = allocate(shape=(128,), dtype=np.uint64)
    main_buffer = []
    reset_pl()
    czt.command("BREAK")
    for _ in range(2):
        czt_temp = czt.command("READ_TEMPERATURE")

    npackets = 1000
    dma_channel.start()
    dma_channel.transfer(event_data_buffer)
    czt.command("EVENT_ON")

    start_time = time.time()
    for i in range(npackets):
        dma_channel.wait()
        main_buffer.extend(event_data_buffer.tolist())
        dma_channel.transfer(event_data_buffer)

    stop_time = time.time()
    time_to_measure_round_1 = stop_time - start_time  # This is in seconds

    czt.command("EVENT_OFF")

    npackets = f"{npackets:04d}"

    parse_main_buffer = common.parse_event_data(main_buffer)
    det = []
    for x in parse_main_buffer:
        det.append(x)

    times_det = [x[0] for x in det]
    pixels_det = [x[2] for x in det]
    energy_det = [x[3] for x in det]

    minutes, secs = divmod(round(time_to_measure_round_1), 60)

    pixhist = np.bincount(pixels_det, minlength=256)
    plt.figure(figsize=(11, 11))
    plt.title('Round 1: Counts measured per pixel for Det (Sr.No. ' + str(det_serial_number) + ")\n "
              + radiation_measured + " spectrum, " + "no. of packets: " + str(
        npackets) + ", time = " + f"{minutes} mins:{secs} secs")
    sns.heatmap(pixhist.reshape((16, 16)), cmap="viridis", linewidths=1, annot=True, fmt=".0f")

    if not os.path.exists(date):
        os.makedirs(date)

    path = date + "//"
    file_name = (date + "_det_" + str(det_serial_number) + "_round_1_" + radiation_measured + "_pkts_" + str(npackets)
                 + "_" + curr_time + "_heatmap.png")

    plt.savefig(path + file_name, dpi=300)

    plt.figure(figsize=(14, 7))
    plt.hist(energy_det, bins=range(0, 4096, 10), alpha=0.5, color='b')
    plt.xlabel("PHA")
    plt.ylabel("Counts")

    path = date + "//"
    file_name = (date + "_det_" + str(det_serial_number) + "_round_1_" + radiation_measured + "_pkts_" + str(npackets)
                 + "_" + curr_time + "_spectrum.png")

    plt.savefig(path + file_name, dpi=300)
    # Generating file name for this round
    file_name = date + "_det_" + str(det_serial_number) + "_round_1_" + radiation_measured + "_pkts_" + str(
        npackets) + "_" + start_time
    file_name=str(file_name)
    file_name_round_1 = file_name + '.txt'

    # Storing measurement data in it
    # Saving of plot
    if not os.path.exists(date):
        os.makedirs(date)
    with open(date + "//" + file_name_round_1, "w") as file:
        file.write(str(main_buffer))
    print('No of disabled pixels is: ', czt.num_disabled)



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


client.write_coil(0, True)
## Program runs from 25 - 20 - 15 - 10 - 5 - 25

det_HV_bias = input("Please enter HV bias voltage set in V: ")
radiation_measured = input("Enter type of radiation which is to be measured (bkg for background): ")

date = input("Enter today's date in YYYYMMDD format: ")
curr_time = input("Current Time")
exp_data = True


## These flags will define if I want to take reading at a temperature
flag1=True
flag2=True
flag3=True
flag4=True
while(exp_data):
    key="TEMP_PV"
    value=register_address_map[key]
    rd=client.read_holding_registers(value)
    tc_temp=float(rd.registers)
    if 24.7 <= tc_temp <=25 and flag1:
        for th in [10, 20, 40, 60]:
            now = datetime.now()
            curr_time = str(now.strftime("%H:%M:%S"))
            for _ in range(2):
                czt_temp = czt.command("READ_TEMPERATURE")
            czt.set_threshold(th)
            generate_data(date, curr_time, radiation_measured)
        flag1=False
        continue
    elif 19.7 <= tc_temp <=20.7 and flag2:
        for th in [10, 20, 40, 60]:
            now = datetime.now()
            curr_time = str(now.strftime("%H:%M:%S"))
            for _ in range(2):
                czt_temp = czt.command("READ_TEMPERATURE")
            czt.set_threshold(th)
            generate_data(date, curr_time, radiation_measured)
        flag2=False
        continue
    elif 14.7 <= tc_temp <=15.7 and flag3:
        for th in [10, 20, 40, 60]:
            now = datetime.now()
            curr_time = str(now.strftime("%H:%M:%S"))
            for _ in range(2):
                czt_temp = czt.command("READ_TEMPERATURE")
            czt.set_threshold(th)
            generate_data(date, curr_time, radiation_measured)
        flag3=False
        continue
    elif 9.7 <= tc_temp <=10.7 and flag4:
        for th in [10, 20, 40, 60]:
            now = datetime.now()
            curr_time = str(now.strftime("%H:%M:%S"))
            for _ in range(2):
                czt_temp = czt.command("READ_TEMPERATURE")
            czt.set_threshold(th)
            generate_data(date, curr_time, radiation_measured)
        flag4=False
        continue
    elif 4.7 <= tc_temp <=5.7 and flag5:
        for th in [10, 20, 40, 60]:
            now = datetime.now()
            curr_time = str(now.strftime("%H:%M:%S"))
            for _ in range(2):
                czt_temp = czt.command("READ_TEMPERATURE")
            czt.set_threshold(th)
            generate_data(date, curr_time, radiation_measured)
        flag5=False
        exp_data=False
        continue

print("Data Generation completed successfully")
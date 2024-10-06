#! /usr/bin/python3

import argparse
import asyncio
import logging
import os
import sys
import datetime
import requests
import socket

from bleak.exc import BleakDBusError

#print(sys.path)
os.environ["RUUVI_BLE_ADAPTER"] = "bleak"

import ruuvitag_sensor
from ruuvitag_sensor.adapters import is_async_adapter
from ruuvitag_sensor.log import log
from ruuvitag_sensor.ruuvi import RuuviTagSensor

ruuvitag_sensor.log.enable_console()

def my_excepthook(exctype, value, traceback):
    sys.__excepthook__(exctype, value, traceback)

    if not issubclass(exctype, KeyboardInterrupt):
        log.critical(value)


sys.excepthook = my_excepthook

# #########################################
# my globals:

names_map = {}
host_address = None

# #########################################
# my functions:

def parse_names_list(filename: str):
    global names_map
    file = open(filename, mode = 'r', encoding = 'utf-8')
    lines = file.readlines()
    file.close()
    for line in lines:
        line = line.strip()
        fields = line.split()
        if len(fields) == 2:
            names_map[fields[0].lower()] = fields[1]


def convert_format(data: dict):
    tags_list = []

    for mac in data.keys():
        name = names_map.get(mac.lower())
        if name is None:
            name = mac
        indata = data[mac]
        tags_list.append({
            'id' : mac,
            'name' : name,
            'dataFormat' : indata['data_format'],
            'humidity' : indata['humidity'],
            'temperature' : indata['temperature'],
            'temperatureOffset' : 0.0,
            'pressure' : indata['pressure'] * 100.0,
            'rssi' : indata['rssi'],
            'voltage' : indata['battery'] * 0.001,
            'accelX' : indata['acceleration_x'] * 0.001,
            'accelY': indata['acceleration_y'] * 0.001,
            'accelZ': indata['acceleration_z'] * 0.001
        })

    output_data = { 'tags': tags_list,
                    'deviceId': socket.gethostname(),
                    'time': datetime.datetime.now().astimezone().isoformat()
    }
    return output_data


def send_output(output:dict):
    x = requests.post(host_address, json= output)
    log.info(f"Request status: {x.status_code}; text: {x.text}")


def write_number_file(filename: str, number: int):
    file = open(filename, mode = 'w', encoding = 'utf-8')
    file.write(f"{number}\n")
    file.close()


def process_data(data: dict, arguments: argparse.Namespace):
    log.info(data)
    output = convert_format(data)
    if host_address is not None:
        send_output(output)
    if arguments.number_file is not None:
        write_number_file(arguments.number_file, len(data.keys()))


# main routines:
async def _async_main_handle(arguments: argparse.Namespace):
    if arguments.mac_address:
        data = await RuuviTagSensor.get_data_for_sensors_async(
            macs=[arguments.mac_address], bt_device=arguments.bt_device
        )
        log.info(data)
    elif arguments.find_action:
        await RuuviTagSensor.find_ruuvitags_async(arguments.bt_device)
    elif arguments.latest_action:
        data = await RuuviTagSensor.get_data_for_sensors_async(bt_device=arguments.bt_device, search_duratio_sec=10)
        process_data(data, arguments)
    elif arguments.stream_action:
        async for mac, sensor_data in RuuviTagSensor.get_data_async(bt_device=arguments.bt_device):
            log.info("%s - %s", mac, sensor_data)


def _sync_main_handle(arguments: argparse.Namespace):
    if arguments.mac_address:
        data = RuuviTagSensor.get_data_for_sensors(macs=[arguments.mac_address], bt_device=arguments.bt_device)
        log.info(data)
    elif arguments.find_action:
        RuuviTagSensor.find_ruuvitags(arguments.bt_device)
    elif arguments.latest_action:
        data = RuuviTagSensor.get_data_for_sensors(bt_device=arguments.bt_device, search_duratio_sec=10)
        process_data(data, arguments)
    elif arguments.stream_action:
        RuuviTagSensor.get_data(lambda x: log.info("%s - %s", x[0], x[1]), bt_device=arguments.bt_device)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--get", dest="mac_address", help="Get data")
    parser.add_argument("-d", "--device", dest="bt_device", help="Set Bluetooth device id (default hci0)")
    parser.add_argument("-f", "--find", action="store_true", dest="find_action", help="Find broadcasting RuuviTags")
    parser.add_argument(
        "-l", "--latest", action="store_true", dest="latest_action", help="Get latest data for found RuuviTags"
    )
    parser.add_argument(
        "-s", "--stream", action="store_true", dest="stream_action", help="Stream broadcasts from all RuuviTags"
    )
    parser.add_argument("-o", "--host", dest="host_address", help="Set host address for HTTP POST of data")
    parser.add_argument("-n", "--names", dest="name_list", help="Set list of sensor names (tab-separated: mac -> name)")
    parser.add_argument("-w", "--write-number", dest="number_file", help="Write number of found sensors into the given file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {ruuvitag_sensor.__version__}")
    parser.add_argument("--debug", action="store_true", dest="debug_action", help="Enable debug logging")
    args = parser.parse_args()

    if args.name_list:
        parse_names_list(args.name_list)

    if args.host_address:
        host_address = args.host_address

    if args.debug_action:
        log.setLevel(logging.DEBUG)
        for handler in log.handlers:
            handler.setLevel(logging.DEBUG)

    if not args.mac_address and not args.find_action and not args.latest_action and not args.stream_action:
        parser.print_usage()
        sys.exit(0)

    try:
        if is_async_adapter(ruuvitag_sensor.ruuvi.ble):
            asyncio.get_event_loop().run_until_complete(_async_main_handle(args))
        else:
            _sync_main_handle(args)
    except BleakDBusError as e:
        # if a Bluetooth exception occurred we will not have received any sensor data.
        log.critical("Bluetooth exception: %s", e)
        if args.number_file is not None:
            write_number_file(args.number_file, 0)



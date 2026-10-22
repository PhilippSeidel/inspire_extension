import serial
import time


regdict = {
    'ID'        : 1000,
    'baudrate'  : 1001,
    'clearErr'  : 1004,
    'forceClb'  : 1009,
    'angleSet'  : 1486,
    'forceSet'  : 1498,
    'speedSet'  : 1522,
    'posAct'    : 1534,
    'angleAct'  : 1546,
    'forceAct'  : 1582,
    'current'   : 1594,
    'errCode'   : 1606,
    'statusCode': 1612,
    'temp'      : 1618,
    'actionSeq' : 2320,
    'actionRun' : 2322
}

def openSerial(port, baudrate):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baudrate
    ser.open()
    return ser

def writeRegister(ser, id, add, num, val):
    bytes = [0xEB, 0x90]
    bytes.append(id) # id
    bytes.append(num + 3) # len
    bytes.append(0x12) # cmd
    bytes.append(add & 0xFF)
    bytes.append((add >> 8) & 0xFF) # add
    for i in range(num):
        bytes.append(val[i])
    checksum = 0x00
    for i in range(2, len(bytes)):
        checksum += bytes[i]
    checksum &= 0xFF
    bytes.append(checksum)
    ser.write(bytes)
    time.sleep(0.01)
    ser.read_all()

def readRegister(ser, id, add, num, mute=False):
    bytes = [0xEB, 0x90]
    bytes.append(id) # id
    bytes.append(0x04) # len
    bytes.append(0x11) # cmd
    bytes.append(add & 0xFF)
    bytes.append((add >> 8) & 0xFF) # add
    bytes.append(num)
    checksum = 0x00
    for i in range(2, len(bytes)):
        checksum += bytes[i]
    checksum &= 0xFF
    bytes.append(checksum)
    ser.write(bytes)
    time.sleep(0.01)
    recv = ser.read_all()
    if len(recv) == 0:
        return []
    num = (recv[3] & 0xFF) - 3
    val = []
    for i in range(num):
        val.append(recv[7 + i])
    if not mute:
        print('The register values ​​read are, in order:', end='')
        for i in range(num):
            print(val[i], end=' ')
        print()
    return val

def write6(ser, device_id, key, values):
    if key not in ['angleSet', 'forceSet', 'speedSet', 'mode']:
        print("Invalid key")
        return
    val_reg = []
    for v in values:
        val_reg.append(v & 0xFF)
        val_reg.append((v >> 8) & 0xFF)
    writeRegister(ser, device_id, regdict[key], 12, val_reg)

def read6(ser, device_id, key):
    if key not in regdict:
        print("Invalid key")
        return None
    raw = readRegister(ser, device_id, regdict[key], 12)
    if not raw or len(raw) < 12:
        print("No or incomplete data received")
        return None
    results = []
    for i in range(6):
        value = raw[2 * i] | (raw[2 * i + 1] << 8)
        if value > 32767:
            value -= 65536
        results.append(value)
    return results

def readTouchData(ser):
    """
    Read touch sensor data from all fingers and palm.
    Returns (finger_results, palm_results) or (None, None) on failure.
    finger_results: dict keyed by finger name, each value is a list of sensor readings.
    palm_results: dict keyed by 'palm_data_1' .. 'palm_data_9'.
    """
    cmd = bytes([0xEB, 0x90, 0x01, 0x04, 0x11, 0xB8, 0x0B, 0x44, 0x1D])
    ser.write(cmd)
    time.sleep(0.025)
    recv = ser.read_all()

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            start_idx = recv.index(0xB8)
            if recv[start_idx + 1] == 0x0B:
                data_start = start_idx + 2
                break
            else:
                print(f"Locate attempt {attempt + 1}: Expected B8 0B not found")
        except ValueError:
            print(f"Locate attempt {attempt + 1}: Touch data address B8 0B not found")
        time.sleep(0.01)
    else:
        return None, None

    fingers = ['little', 'ring', 'middle', 'index', 'thumb']
    finger_results = {}

    for i, finger in enumerate(fingers):
        base_idx = data_start + i * 10
        bytes_data = recv[base_idx:base_idx + 10]
        data_bytes = [
            (bytes_data[j] | (bytes_data[j + 1] << 8)) for j in range(0, 6, 2)
        ]
        combined_value = (bytes_data[6] | (bytes_data[7] << 8) | (bytes_data[8] << 16))
        data_bytes.append(combined_value)
        finger_results[finger] = data_bytes

    palm_results = {}
    palm_start_idx = data_start + len(fingers) * 10

    if palm_start_idx + 17 < len(recv):
        palm_data = [recv[palm_start_idx + j] for j in range(18)]
        for j in range(9):
            value = palm_data[j * 2] | (palm_data[j * 2 + 1] << 8)
            palm_results[f'palm_data_{j + 1}'] = value
    else:
        print("Palm data out of bounds, unable to read")

    ser.read_all()
    return finger_results, palm_results


if __name__ == '__main__':
    ser = openSerial('/dev/ttyUSB0', 115200)
    write6(ser, 1, 'speedSet', [100, 100, 100, 100, 100, 100])
    time.sleep(2)
    write6(ser, 1, 'forceSet', [500, 500, 500, 500, 500, 500])
    time.sleep(1)
    write6(ser, 1, 'angleSet', [0, 0, 0, 0, 400, -1])
    time.sleep(3)
    read6(ser, 1, 'angleAct')
    time.sleep(1)
    write6(ser, 1, 'angleSet', [1000, 1000, 1000, 1000, 400, -1])
    time.sleep(3)
    read6(ser, 1, 'angleAct')
    time.sleep(1)
    read6(ser, 1, 'errCode')
